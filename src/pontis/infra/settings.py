# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent application settings management for Pontis."""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from pontis.infra.paths import config_dir

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS_FILENAME = "settings.json"


@dataclass
class AppSettings:
    """User-configurable application settings."""

    language: str = "system"  # "system", "en", or "pt_BR"
    theme: str = "system"  # "system", "light", or "dark"
    rclone_path: str = ""  # Custom rclone binary path (empty = auto-detect)
    check_updates_on_startup: bool = True
    ignored_update_version: str = ""
    last_update_check: str = ""

    def validate(self) -> None:
        """Sanitize and validate configuration values."""
        if self.language not in ("system", "en", "pt_BR"):
            self.language = "system"
        if self.theme not in ("system", "light", "dark"):
            self.theme = "system"


class SettingsManager:
    """Loads and saves AppSettings to a JSON file."""

    def __init__(self, file_path: Path | None = None) -> None:
        self._path = file_path or (config_dir() / DEFAULT_SETTINGS_FILENAME)

    @property
    def file_path(self) -> Path:
        """Return the target settings JSON path."""
        return self._path

    def load(self) -> AppSettings:
        """Load settings from disk or return default settings if missing/invalid."""
        if not self._path.is_file():
            settings = AppSettings()
            return settings

        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("Corrupted settings file at %s; using defaults.", self._path)
                return AppSettings()

            settings = AppSettings(
                language=str(data.get("language", "system")),
                theme=str(data.get("theme", "system")),
                rclone_path=str(data.get("rclone_path", "")),
                check_updates_on_startup=bool(data.get("check_updates_on_startup", True)),
                ignored_update_version=str(data.get("ignored_update_version", "")),
                last_update_check=str(data.get("last_update_check", "")),
            )
            settings.validate()
            return settings
        except Exception as exc:
            logger.warning("Failed to parse settings at %s: %s; using defaults.", self._path, exc)
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        """Persist settings to disk atomically."""
        settings.validate()
        data = asdict(settings)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write via temporary file
        temp_dir = self._path.parent
        with tempfile.NamedTemporaryFile(
            "w",
            dir=temp_dir,
            delete=False,
            encoding="utf-8",
            prefix="settings_",
            suffix=".tmp",
        ) as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp_path = Path(tmp.name)

        tmp_path.replace(self._path)


_default_manager: SettingsManager | None = None


def get_settings_manager() -> SettingsManager:
    """Return the global default settings manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = SettingsManager()
    return _default_manager


def load_settings() -> AppSettings:
    """Convenience helper to load the active app settings."""
    return get_settings_manager().load()


def save_settings(settings: AppSettings) -> None:
    """Convenience helper to persist app settings."""
    get_settings_manager().save(settings)
