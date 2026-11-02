# SPDX-License-Identifier: GPL-3.0-or-later
"""Run orchestration: lock, safety checks, rclone execution and history."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pontis.domain.models import (
    EndpointKind,
    RunResult,
    RunStatus,
    SyncDirection,
    SyncProfile,
    utcnow,
)
from pontis.infra.locking import ProfileLock
from pontis.infra.rclone_adapter import AdapterOutcome, EventCallback, LogEvent, RcloneAdapter
from pontis.infra.repositories import RunRepository
from pontis.infra.run_logger import RunLogManager


class RunError(Exception):
    """Base class for refusals raised before rclone is started."""


class EndpointMissingError(RunError):
    """A local folder of the profile does not exist (e.g. unmounted disk)."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path


class FirstRunDryRunRequiredError(RunError):
    """The first real run needs a successful ``--dry-run`` beforehand."""


class RunService:
    """Runs profiles through :class:`RcloneAdapter` and records the history."""

    def __init__(
        self,
        adapter: RcloneAdapter,
        runs: RunRepository,
        lock_dir: Path,
        log_manager: RunLogManager | None = None,
    ) -> None:
        self._adapter = adapter
        self._runs = runs
        self._lock_dir = lock_dir
        self._log_manager = log_manager if log_manager is not None else RunLogManager()
        self.last_outcome: AdapterOutcome | None = None

    @property
    def log_manager(self) -> RunLogManager:
        """Return the active log manager."""
        return self._log_manager

    def cancel(self) -> None:
        """Cancel the active rclone process, if any."""
        self._adapter.cancel()

    def get_run_log(self, run_id: int) -> str:
        """Read the execution log text for a specific run ID."""
        return self._log_manager.get_run_log(run_id)

    def export_run_log(self, run_id: int, target_path: Path) -> None:
        """Export the execution log of a run to a destination path."""
        self._log_manager.export_log(run_id, target_path)

    def needs_first_run_dry_run(self, profile: SyncProfile) -> bool:
        """Return True if the profile requires a successful initial dry-run."""
        if profile.id is None:
            return False
        return self._adapter.needs_resync(profile) and not self._has_successful_dry_run(profile.id)

    def run(
        self,
        profile: SyncProfile,
        *,
        dry_run: bool = False,
        require_dry_run_first: bool = True,
        force: bool = False,
        resync: bool = False,
        on_event: EventCallback | None = None,
        on_outcome: Callable[[AdapterOutcome], None] | None = None,
    ) -> RunResult:
        """Run one profile and return the persisted :class:`RunResult`.

        Raises :class:`ProfileLockedError` if the profile is already running,
        :class:`RunError` subclasses for failed safety checks, and propagates
        ``KeyboardInterrupt`` after recording the run as cancelled.
        """
        if profile.id is None:
            raise ValueError("Profile must be saved before running.")
        with ProfileLock(self._lock_dir, profile.id):
            self._check_endpoints(profile)
            if (
                require_dry_run_first
                and not dry_run
                and not resync
                and self._adapter.needs_resync(profile)
                and not self._has_successful_dry_run(profile.id)
            ):
                raise FirstRunDryRunRequiredError(profile.name)

            result = self._runs.add(RunResult(profile_id=profile.id, dry_run=dry_run))
            assert result.id is not None
            cmd = self._adapter.build_command(
                profile,
                dry_run=dry_run,
                force=force,
                resync=True if resync else None,
            )
            log_writer = self._log_manager.create_writer(
                result.id,
                profile.name,
                dry_run=dry_run,
                command=cmd,
            )

            def _log_event_handler(event: LogEvent) -> None:
                log_writer.write_event(event)
                if on_event is not None:
                    on_event(event)

            try:
                outcome = self._adapter.run(
                    profile,
                    dry_run=dry_run,
                    force=force,
                    resync=True if resync else None,
                    on_event=_log_event_handler,
                )
                if (
                    outcome.is_too_many_deletes
                    and not force
                    and outcome.detected_deletes_count <= profile.options.max_delete_files
                ):
                    # Transparently re-run with force when within safety tolerance
                    # (e.g. rename or minor deletions in small folders).
                    outcome = self._adapter.run(
                        profile,
                        dry_run=dry_run,
                        force=True,
                        resync=True if resync else None,
                        on_event=_log_event_handler,
                    )
                self.last_outcome = outcome
                if on_outcome is not None:
                    on_outcome(outcome)
            except KeyboardInterrupt:
                self._finish(result, RunStatus.CANCELLED, "cancelled")
                log_writer.finish(RunStatus.CANCELLED, 0, 0, 0, "cancelled")
                raise
            except BaseException as exc:
                self._finish(result, RunStatus.ERROR, str(exc))
                log_writer.finish(RunStatus.ERROR, 0, 0, 1, str(exc))
                raise

            result.files_transferred = outcome.planned_copies if dry_run else outcome.transfers
            result.files_deleted = outcome.planned_deletes if dry_run else outcome.deletes
            result.errors = outcome.errors

            if outcome.returncode in (-15, -9, 130, 143):
                final_res = self._finish(result, RunStatus.CANCELLED, "cancelled")
            elif outcome.returncode == 0:
                final_res = self._finish(result, RunStatus.SUCCESS, "")
            else:
                message = (
                    "\n".join(outcome.error_messages[-5:]) or f"rclone exit {outcome.returncode}"
                )
                final_res = self._finish(result, RunStatus.ERROR, message)

            log_writer.finish(
                final_res.status,
                final_res.files_transferred,
                final_res.files_deleted,
                final_res.errors,
                final_res.message,
            )
            self._log_manager.prune_logs()
            return final_res

    def _finish(self, result: RunResult, status: RunStatus, message: str) -> RunResult:
        result.status = status
        result.message = message
        result.finished_at = utcnow()
        return self._runs.update(result)

    def _has_successful_dry_run(self, profile_id: int) -> bool:
        return any(
            r.dry_run and r.status is RunStatus.SUCCESS
            for r in self._runs.list_for_profile(profile_id)
        )

    @staticmethod
    def _check_endpoints(profile: SyncProfile) -> None:
        direction = profile.options.direction
        if direction is SyncDirection.A_TO_B:
            sides = [profile.side_a]  # the destination may be created by rclone
        elif direction is SyncDirection.B_TO_A:
            sides = [profile.side_b]
        else:
            sides = [profile.side_a, profile.side_b]
        for side in sides:
            if side.kind is EndpointKind.LOCAL and not Path(side.path).expanduser().is_dir():
                raise EndpointMissingError(side.path)
