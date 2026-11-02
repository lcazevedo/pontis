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
from pontis.infra.rclone_adapter import AdapterOutcome, EventCallback, RcloneAdapter
from pontis.infra.repositories import RunRepository


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
    ) -> None:
        self._adapter = adapter
        self._runs = runs
        self._lock_dir = lock_dir
        self.last_outcome: AdapterOutcome | None = None

    def cancel(self) -> None:
        """Cancel the active rclone process, if any."""
        self._adapter.cancel()

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
                and self._adapter.needs_resync(profile)
                and not self._has_successful_dry_run(profile.id)
            ):
                raise FirstRunDryRunRequiredError(profile.name)

            result = self._runs.add(RunResult(profile_id=profile.id, dry_run=dry_run))
            try:
                outcome = self._adapter.run(profile, dry_run=dry_run, on_event=on_event)
                self.last_outcome = outcome
                if on_outcome is not None:
                    on_outcome(outcome)
            except KeyboardInterrupt:
                self._finish(result, RunStatus.CANCELLED, "cancelled")
                raise
            except BaseException as exc:
                self._finish(result, RunStatus.ERROR, str(exc))
                raise

            result.files_transferred = outcome.planned_copies if dry_run else outcome.transfers
            result.files_deleted = outcome.planned_deletes if dry_run else outcome.deletes
            result.errors = outcome.errors

            if outcome.returncode in (-15, -9, 130, 143):
                return self._finish(result, RunStatus.CANCELLED, "cancelled")
            if outcome.returncode == 0:
                return self._finish(result, RunStatus.SUCCESS, "")
            message = "\n".join(outcome.error_messages[-5:]) or f"rclone exit {outcome.returncode}"
            return self._finish(result, RunStatus.ERROR, message)

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
