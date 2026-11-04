# SPDX-License-Identifier: GPL-3.0-or-later
"""Real-time file system observation using watchdog with debounce.

Allows monitoring a sync profile's local folders for changes and triggering
synchronization automatically after a configurable debounce period.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pontis.domain.models import EndpointKind, SyncProfile

logger = logging.getLogger(__name__)

# Patterns always ignored regardless of profile configuration
_IGNORED_SYSTEM_PATTERNS = (
    ".git/*",
    "*/.git/*",
    ".rclone-bisync*",
    "*/.rclone-bisync*",
    "*.swp",
    "*.tmp",
    "*~",
    "RCLONE_TEST",
    "*/RCLONE_TEST",
)


class WatchdogUnavailableError(Exception):
    """Raised when watchdog is not installed in the environment."""


class ProfileWatchError(Exception):
    """Raised when a profile cannot be watched (e.g. no local endpoints)."""


class ProfileWatchHandler:
    """Internal file system event handler that applies filters and debounce."""

    def __init__(
        self,
        profile: SyncProfile,
        base_dir: Path,
        debounce_seconds: float = 5.0,
        on_change: Callable[[str, str], None] | None = None,
        on_sync_triggered: Callable[[SyncProfile], None] | None = None,
    ) -> None:
        self.profile = profile
        self.base_dir = base_dir.resolve()
        self.debounce_seconds = max(0.01, debounce_seconds)
        self.on_change = on_change
        self.on_sync_triggered = on_sync_triggered

        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._is_syncing = False
        self._pending_sync_after_finish = False
        self._stopped = False

    def _should_ignore(self, path_str: str) -> bool:
        """Check whether a modified path matches internal or profile exclude patterns."""
        try:
            rel = os.path.relpath(path_str, self.base_dir)
        except ValueError:
            rel = path_str

        # Normalize path separators
        norm_rel = rel.replace("\\", "/")

        for pat in _IGNORED_SYSTEM_PATTERNS:
            if fnmatch.fnmatch(norm_rel, pat) or fnmatch.fnmatch(os.path.basename(path_str), pat):
                return True

        for pat in self.profile.options.excludes:
            clean_pat = pat.strip()
            if not clean_pat:
                continue
            if fnmatch.fnmatch(norm_rel, clean_pat) or fnmatch.fnmatch(
                os.path.basename(path_str), clean_pat
            ):
                return True
        return False

    def dispatch(self, event: Any) -> None:
        """Process a watchdog file system event."""
        if self._stopped:
            return

        is_directory = getattr(event, "is_directory", False)
        if is_directory:
            return

        src_path = str(getattr(event, "src_path", ""))
        event_type = str(getattr(event, "event_type", "modified"))

        if not src_path or self._should_ignore(src_path):
            return

        if self.on_change:
            try:
                self.on_change(event_type, src_path)
            except Exception as err:
                logger.warning("Error in on_change callback: %s", err)

        self._schedule_sync()

    def _schedule_sync(self) -> None:
        """Reset or schedule the debounce timer."""
        with self._lock:
            if self._stopped:
                return
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._fire_sync)
            self._timer.daemon = True
            self._timer.start()

    def _fire_sync(self) -> None:
        """Debounce timer expired: trigger synchronization."""
        with self._lock:
            if self._stopped:
                return
            if self._is_syncing:
                self._pending_sync_after_finish = True
                return
            self._is_syncing = True

        try:
            if self.on_sync_triggered:
                self.on_sync_triggered(self.profile)
        finally:
            with self._lock:
                self._is_syncing = False
                has_pending = self._pending_sync_after_finish
                self._pending_sync_after_finish = False

            if has_pending and not self._stopped:
                self._schedule_sync()

    def stop(self) -> None:
        """Cancel any pending debounce timer and mark handler as stopped."""
        with self._lock:
            self._stopped = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


class WatchService:
    """Manages filesystem watchers for sync profiles."""

    def __init__(self) -> None:
        self._observers: dict[int, Any] = {}
        self._handlers: dict[int, list[ProfileWatchHandler]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def get_watchable_paths(profile: SyncProfile) -> list[Path]:
        """Return existing local folder paths belonging to this profile."""
        paths: list[Path] = []
        for side in (profile.side_a, profile.side_b):
            if side.kind == EndpointKind.LOCAL and side.path:
                p = Path(side.path).expanduser().resolve()
                if p.is_dir():
                    paths.append(p)
        return paths

    def start_watching(
        self,
        profile: SyncProfile,
        debounce_seconds: float = 5.0,
        on_change: Callable[[str, str], None] | None = None,
        on_sync_triggered: Callable[[SyncProfile], None] | None = None,
    ) -> list[Path]:
        """Start monitoring a profile's local directories.

        Returns the list of monitored directories.
        """
        try:
            from watchdog.events import FileSystemEventHandler  # noqa: F401
            from watchdog.observers import Observer
        except ImportError as err:
            raise WatchdogUnavailableError(
                "The 'watchdog' library is required for real-time folder observation."
            ) from err

        profile_key = profile.id if profile.id is not None else hash(profile.name)
        with self._lock:
            if profile_key in self._observers:
                self.stop_watching(profile_key)

            watchable = self.get_watchable_paths(profile)
            if not watchable:
                raise ProfileWatchError(
                    f"Profile '{profile.name}' has no accessible local folder to watch."
                )

            observer = Observer()
            handlers: list[ProfileWatchHandler] = []

            for folder in watchable:
                handler = ProfileWatchHandler(
                    profile=profile,
                    base_dir=folder,
                    debounce_seconds=debounce_seconds,
                    on_change=on_change,
                    on_sync_triggered=on_sync_triggered,
                )

                class _BridgeHandler(FileSystemEventHandler):
                    def __init__(self, target: ProfileWatchHandler) -> None:
                        super().__init__()
                        self._target = target

                    def on_any_event(self, event: Any) -> None:
                        self._target.dispatch(event)

                observer.schedule(_BridgeHandler(handler), str(folder), recursive=True)
                handlers.append(handler)

            observer.daemon = True
            observer.start()

            self._observers[profile_key] = observer
            self._handlers[profile_key] = handlers
            return watchable

    def stop_watching(self, profile_key: int) -> bool:
        """Stop watching a profile by id or key."""
        with self._lock:
            observer = self._observers.pop(profile_key, None)
            handlers = self._handlers.pop(profile_key, [])
            if observer is not None:
                for h in handlers:
                    h.stop()
                try:
                    observer.stop()
                    observer.join(timeout=2.0)
                except Exception as err:
                    logger.warning("Error stopping observer for profile %s: %s", profile_key, err)
                return True
            return False

    def is_watching(self, profile_key: int) -> bool:
        """Check if a profile is currently being watched."""
        with self._lock:
            return profile_key in self._observers

    def stop_all(self) -> None:
        """Stop all active watchers."""
        with self._lock:
            keys = list(self._observers.keys())
        for key in keys:
            self.stop_watching(key)
