# SPDX-License-Identifier: GPL-3.0-or-later
"""Background worker thread for running rclone sync executions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QThread, Signal

from pontis.i18n import tr
from pontis.infra.locking import ProfileLockedError
from pontis.services.run_service import EndpointMissingError, RunError

if TYPE_CHECKING:
    from pontis.domain.models import SyncProfile
    from pontis.infra.rclone_adapter import AdapterOutcome, LogEvent
    from pontis.services.run_service import RunService


class SyncWorker(QThread):
    """Executes a sync profile via :class:`RunService` in a dedicated QThread."""

    progress_signal = Signal(dict)
    log_signal = Signal(str, str)
    finished_signal = Signal(object, object)  # (RunResult, AdapterOutcome | None)
    error_signal = Signal(str)
    cancelled_signal = Signal()

    def __init__(
        self,
        profile: SyncProfile,
        run_service: RunService,
        *,
        dry_run: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._run_service = run_service
        self._dry_run = dry_run
        self._is_cancelled = False

    @property
    def profile(self) -> SyncProfile:
        """Return the profile being synchronized."""
        return self._profile

    @property
    def dry_run(self) -> bool:
        """Return whether this execution is a simulation."""
        return self._dry_run

    def cancel(self) -> None:
        """Request immediate termination of the running sync process."""
        self._is_cancelled = True
        self._run_service.cancel()
        self.cancelled_signal.emit()

    def run(self) -> None:
        """Thread execution body."""
        outcome_holder: list[AdapterOutcome | None] = [None]

        def _on_event(event: LogEvent) -> None:
            data: dict[str, Any] = {
                "level": event.level,
                "message": event.message,
                "object": event.obj,
            }
            if event.stats is not None:
                data.update(event.stats)
            self.progress_signal.emit(data)
            self.log_signal.emit(event.level, event.message)

        def _on_outcome(outcome: AdapterOutcome) -> None:
            outcome_holder[0] = outcome

        try:
            result = self._run_service.run(
                self._profile,
                dry_run=self._dry_run,
                require_dry_run_first=False,
                on_event=_on_event,
                on_outcome=_on_outcome,
            )
            outcome = outcome_holder[0] or self._run_service.last_outcome
            self.finished_signal.emit(result, outcome)
        except ProfileLockedError:
            self.error_signal.emit(tr("ui.alert.already_running", name=self._profile.name))
        except EndpointMissingError as exc:
            self.error_signal.emit(tr("ui.alert.endpoint_missing", path=exc.path))
        except RunError as exc:
            self.error_signal.emit(str(exc))
        except Exception as exc:
            if not self._is_cancelled:
                self.error_signal.emit(str(exc))
