# SPDX-License-Identifier: GPL-3.0-or-later
"""Real-time progress dialog for sync executions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pontis.domain.models import ConflictPolicy, RunStatus
from pontis.i18n import tr
from pontis.ui.dry_run_summary_dialog import DryRunSummaryDialog
from pontis.ui.icons import get_icon
from pontis.ui.notifications import send_notification
from pontis.ui.sync_worker import SyncWorker

if TYPE_CHECKING:
    from pontis.domain.models import RunResult, SyncProfile
    from pontis.infra.rclone_adapter import AdapterOutcome
    from pontis.services.run_service import RunService


def _format_bytes(bytes_count: int) -> str:
    """Format bytes into a human-readable string."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    kb = bytes_count / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f} MB"
    gb = mb / 1024
    return f"{gb:.2f} GB"


class SyncProgressDialog(QDialog):
    """Modal dialog displaying live progress, logs, metrics and cancel action."""

    run_finished = Signal(object, object)  # (RunResult, AdapterOutcome | None)
    apply_real_sync_requested = Signal()
    force_sync_requested = Signal(bool)
    resync_requested = Signal()
    resolve_conflicts_requested = Signal()

    def __init__(
        self,
        profile: SyncProfile,
        run_service: RunService,
        *,
        dry_run: bool = False,
        force: bool = False,
        resync: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._run_service = run_service
        self._dry_run = dry_run
        self._force = force
        self._resync = resync
        self._is_active = True
        self._result: RunResult | None = None
        self._outcome: AdapterOutcome | None = None

        title_key = "ui.progress.title_dry_run" if dry_run else "ui.progress.title_sync"
        self.setWindowTitle(tr(title_key, name=profile.name))
        self.resize(700, 520)
        self.setWindowIcon(get_icon("media-playback-start" if not dry_run else "view-refresh"))

        self._init_ui()
        self._start_worker()

    @property
    def run_result(self) -> RunResult | None:
        """Return the completed execution result."""
        return self._result

    @property
    def outcome(self) -> AdapterOutcome | None:
        """Return the detailed adapter outcome."""
        return self._outcome

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header with badge and profile info
        header_layout = QHBoxLayout()
        icon_lbl = QLabel(self)
        icon_name = "weather-clear" if self._dry_run else "media-playback-start"
        icon_lbl.setPixmap(get_icon(icon_name).pixmap(28, 28))
        header_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        self._title_label = QLabel(f"<b>{self._profile.name}</b>", self)
        self._title_label.setStyleSheet("font-size: 14px;")
        self._badge_label = QLabel(
            tr("ui.progress.badge_dry_run" if self._dry_run else "ui.progress.badge_sync"), self
        )
        badge_color = "#f57c00" if self._dry_run else "#2e7d32"
        self._badge_label.setStyleSheet(
            f"font-size: 11px; font-weight: bold; color: {badge_color};"
        )
        title_box.addWidget(self._title_label)
        title_box.addWidget(self._badge_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Status text
        self._status_label = QLabel(tr("ui.progress.status_starting"), self)
        self._status_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self._status_label)

        # Progress bar (indeterminate initially)
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setTextVisible(True)
        layout.addWidget(self._progress_bar)

        # Metrics card
        metrics_frame = QFrame(self)
        metrics_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(metrics_frame)
        grid.setContentsMargins(10, 8, 10, 8)

        # Transfers metric
        transfers_title = (
            tr("ui.progress.metric_planned_transfers")
            if self._dry_run
            else tr("ui.progress.metric_transfers")
        )
        grid.addWidget(QLabel(f"<b>{transfers_title}:</b>", self), 0, 0)
        self._lbl_transfers = QLabel("0", self)
        grid.addWidget(self._lbl_transfers, 0, 1)

        # Deletes metric
        deletes_title = (
            tr("ui.progress.metric_planned_deletes")
            if self._dry_run
            else tr("ui.progress.metric_deletes")
        )
        grid.addWidget(QLabel(f"<b>{deletes_title}:</b>", self), 0, 2)
        self._lbl_deletes = QLabel("0", self)
        grid.addWidget(self._lbl_deletes, 0, 3)

        # Errors metric
        grid.addWidget(QLabel(f"<b>{tr('ui.progress.metric_errors')}:</b>", self), 1, 0)
        self._lbl_errors = QLabel("0", self)
        grid.addWidget(self._lbl_errors, 1, 1)

        # Speed metric
        grid.addWidget(QLabel(f"<b>{tr('ui.progress.metric_speed')}:</b>", self), 1, 2)
        self._lbl_speed = QLabel("—", self)
        grid.addWidget(self._lbl_speed, 1, 3)

        # Bytes metric
        grid.addWidget(QLabel(f"<b>{tr('ui.progress.metric_bytes')}:</b>", self), 2, 0)
        self._lbl_bytes = QLabel("—", self)
        grid.addWidget(self._lbl_bytes, 2, 1)

        layout.addWidget(metrics_frame)

        # Log section
        layout.addWidget(QLabel(f"<b>{tr('ui.progress.log_section')}</b>", self))
        self._log_edit = QPlainTextEdit(self)
        self._log_edit.setReadOnly(True)
        self._log_edit.setStyleSheet(
            "font-family: monospace; font-size: 11px; background-color: rgba(0, 0, 0, 0.03);"
        )
        layout.addWidget(self._log_edit)

        # Action buttons
        btn_layout = QHBoxLayout()
        self._btn_summary = QPushButton(
            get_icon("dialog-information"), tr("ui.progress.btn_show_summary"), self
        )
        self._btn_summary.setVisible(False)
        self._btn_summary.clicked.connect(self._on_show_summary)
        btn_layout.addWidget(self._btn_summary)

        self._btn_force = QPushButton(
            get_icon("security-high"), tr("ui.progress.btn_authorize_deletions"), self
        )
        self._btn_force.setVisible(False)
        self._btn_force.setStyleSheet("font-weight: bold; color: #0277bd;")
        self._btn_force.clicked.connect(self._on_force_clicked)
        btn_layout.addWidget(self._btn_force)

        self._btn_resync = QPushButton(get_icon("view-refresh"), tr("ui.progress.btn_resync"), self)
        self._btn_resync.setVisible(False)
        self._btn_resync.setStyleSheet("font-weight: bold; color: #e65100;")
        self._btn_resync.clicked.connect(self._on_resync_clicked)
        btn_layout.addWidget(self._btn_resync)

        self._btn_conflicts = QPushButton(
            get_icon("emblem-important"), tr("ui.progress.btn_resolve_conflicts"), self
        )
        self._btn_conflicts.setVisible(False)
        self._btn_conflicts.setStyleSheet("font-weight: bold; color: #ef6c00;")
        self._btn_conflicts.clicked.connect(self._on_conflicts_clicked)
        btn_layout.addWidget(self._btn_conflicts)

        btn_layout.addStretch()

        self._btn_cancel = QPushButton(get_icon("process-stop"), tr("ui.progress.btn_cancel"), self)
        self._btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._btn_cancel)

        self._btn_close = QPushButton(tr("ui.progress.btn_close"), self)
        self._btn_close.setVisible(False)
        self._btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_close)

        layout.addLayout(btn_layout)

    def _start_worker(self) -> None:
        self._worker = SyncWorker(
            self._profile,
            self._run_service,
            dry_run=self._dry_run,
            force=self._force,
            resync=self._resync,
            parent=self,
        )
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.log_signal.connect(self._on_log)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.error_signal.connect(self._on_error)
        self._worker.cancelled_signal.connect(self._on_worker_cancelled)
        self._worker.start()

    def _on_progress(self, data: dict[str, Any]) -> None:
        msg = data.get("message", "")
        if "Synching" in msg or "Building" in msg or "checking for diffs" in msg:
            self._status_label.setText(tr("ui.progress.status_comparing"))
        elif "Copying" in msg or "Transferring" in msg:
            self._status_label.setText(tr("ui.progress.status_transferring"))

        transfers = data.get("transfers")
        if transfers is not None:
            self._lbl_transfers.setText(str(transfers))

        deletes = data.get("deletes")
        if deletes is not None:
            self._lbl_deletes.setText(str(deletes))

        errors = data.get("errors")
        if errors is not None:
            self._lbl_errors.setText(str(errors))

        speed = data.get("speed")
        if speed is not None and isinstance(speed, int | float) and speed > 0:
            self._lbl_speed.setText(f"{_format_bytes(int(speed))}/s")

        bytes_val = data.get("bytes")
        total_bytes = data.get("totalBytes")
        if bytes_val is not None:
            if total_bytes is not None and total_bytes > 0:
                self._lbl_bytes.setText(
                    f"{_format_bytes(int(bytes_val))} / {_format_bytes(int(total_bytes))}"
                )
                self._progress_bar.setRange(0, 100)
                pct = min(100, int((bytes_val / total_bytes) * 100))
                self._progress_bar.setValue(pct)
            else:
                self._lbl_bytes.setText(_format_bytes(int(bytes_val)))

    def _on_log(self, level: str, message: str) -> None:
        if not message.strip():
            return
        prefix = f"[{level.upper()}] " if level in ("error", "warning", "critical") else ""
        self._log_edit.appendPlainText(f"{prefix}{message}")

    def _on_finished(self, result: RunResult, outcome: AdapterOutcome | None) -> None:
        self._is_active = False
        self._result = result
        self._outcome = outcome

        self._progress_bar.setRange(0, 100)
        self._btn_cancel.setVisible(False)
        self._btn_close.setVisible(True)

        if outcome:
            if self._dry_run:
                self._lbl_transfers.setText(str(outcome.planned_copies))
                self._lbl_deletes.setText(str(outcome.planned_deletes))
            else:
                self._lbl_transfers.setText(str(outcome.transfers))
                self._lbl_deletes.setText(str(outcome.deletes))
            self._lbl_errors.setText(str(outcome.errors))

        if result.status == RunStatus.SUCCESS:
            self._progress_bar.setValue(100)
            if self._dry_run:
                self._status_label.setText(f"✓ {tr('ui.progress.status_success_dry')}")
                self._status_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
                self._btn_summary.setVisible(True)
                send_notification(
                    tr("ui.notify.dry_success_title"),
                    tr(
                        "ui.notify.dry_success_msg",
                        name=self._profile.name,
                        count=result.files_transferred,
                    ),
                )
            else:
                self._status_label.setText(f"✓ {tr('ui.progress.status_success')}")
                self._status_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
                send_notification(
                    tr("ui.notify.sync_success_title"),
                    tr(
                        "ui.notify.sync_success_msg",
                        name=self._profile.name,
                        count=result.files_transferred,
                    ),
                )
        elif result.status == RunStatus.CANCELLED:
            self._progress_bar.setValue(0)
            self._status_label.setText(tr("ui.progress.status_cancelled"))
            self._status_label.setStyleSheet("color: #e65100; font-weight: bold;")
        else:
            self._progress_bar.setValue(0)
            is_too_many = (
                outcome.is_too_many_deletes
                if outcome is not None
                else ("too many deletes" in result.message.lower())
            )
            if is_too_many:
                count = (
                    outcome.detected_deletes_count
                    if outcome is not None and outcome.detected_deletes_count > 0
                    else max(1, len(outcome.planned_delete_files) if outcome is not None else 1)
                )
                limit = self._profile.options.max_delete_files
                self._status_label.setText(
                    f"🛡️ {tr('ui.progress.status_safety_pause', count=count)}"
                )
                self._status_label.setStyleSheet("color: #0277bd; font-weight: bold;")
                self._btn_force.setText(f"🛡️ {tr('ui.progress.btn_authorize_deletions')}")
                self._btn_force.setVisible(True)
                self._log_edit.appendPlainText(
                    tr("ui.progress.log_safety_protection_note", count=count, limit=limit)
                )
                send_notification(
                    tr("ui.notify.safety_pause_title"),
                    tr("ui.notify.safety_pause_msg", name=self._profile.name, count=count),
                    is_error=False,
                )
            elif (outcome is not None and outcome.needs_resync) or (
                "resync" in result.message.lower() and "must run" in result.message.lower()
            ):
                self._status_label.setText(tr("ui.progress.status_resync_needed"))
                self._status_label.setStyleSheet("color: #e65100; font-weight: bold;")
                self._btn_resync.setVisible(True)
                send_notification(
                    tr("ui.notify.error_title"),
                    tr("ui.progress.status_resync_needed"),
                    is_error=True,
                )
            else:
                self._status_label.setText(f"✗ {tr('ui.progress.status_error')}")
                self._status_label.setStyleSheet("color: #c62828; font-weight: bold;")
                send_notification(
                    tr("ui.notify.error_title"),
                    tr("ui.notify.error_msg", name=self._profile.name),
                    is_error=True,
                )

        if outcome is not None and outcome.has_conflicts:
            count = len(outcome.conflicts_detected)
            if self._profile.options.conflict_policy == ConflictPolicy.KEEP_BOTH:
                self._log_edit.appendPlainText(
                    f"ℹ️ {tr('ui.progress.conflicts_kept_both_log', count=count)}"
                )
            else:
                btn_lbl = f"⚠️ {tr('ui.progress.btn_resolve_conflicts')} ({count})"
                self._btn_conflicts.setText(btn_lbl)
                self._btn_conflicts.setVisible(True)

        self.run_finished.emit(result, outcome)

    def _on_resync_clicked(self) -> None:
        """Handle user request to explicitly initiate a bisync --resync."""
        reply = QMessageBox.question(
            self,
            tr("ui.dialog.resync_confirm.title"),
            tr("ui.dialog.resync_confirm.message"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.resync_requested.emit()
            self.accept()

    def _on_conflicts_clicked(self) -> None:
        """Open the conflict resolution dialog."""
        from pontis.ui.conflict_resolution_dialog import ConflictResolutionDialog

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            dialog = ConflictResolutionDialog(self._profile, parent=self)
        finally:
            QApplication.restoreOverrideCursor()

        if dialog.exec() and dialog.should_sync_after:
            self.apply_real_sync_requested.emit()
            self.accept()

    def _on_force_clicked(self) -> None:
        count = (
            self._outcome.detected_deletes_count
            if self._outcome is not None and self._outcome.detected_deletes_count > 0
            else max(1, len(self._outcome.planned_delete_files) if self._outcome else 1)
        )
        limit = self._profile.options.max_delete_files
        reply = QMessageBox.question(
            self,
            tr("ui.progress.safety_confirm_title"),
            tr("ui.progress.safety_confirm_prompt", count=count, limit=limit),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.force_sync_requested.emit(self._dry_run)
            self.accept()

    def _on_error(self, message: str) -> None:
        self._is_active = False
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._status_label.setText(f"✗ {tr('ui.progress.status_error')}")
        self._status_label.setStyleSheet("color: #c62828; font-weight: bold;")
        self._log_edit.appendPlainText(f"[ERROR] {message}")
        self._btn_cancel.setVisible(False)
        self._btn_close.setVisible(True)
        send_notification(
            tr("ui.notify.error_title"),
            tr("ui.notify.error_msg", name=self._profile.name),
            is_error=True,
        )

    def _on_worker_cancelled(self) -> None:
        self._status_label.setText(tr("ui.progress.cancelling"))
        self._btn_cancel.setEnabled(False)

    def _on_cancel(self) -> None:
        if not self._is_active:
            self.reject()
            return
        reply = QMessageBox.question(
            self,
            tr("ui.progress.btn_cancel"),
            tr("ui.progress.cancel_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._worker.cancel()

    def _on_show_summary(self) -> None:
        summary_dialog = DryRunSummaryDialog(self._profile, self._outcome, parent=self)
        if summary_dialog.exec() and summary_dialog.should_apply_sync:
            self.apply_real_sync_requested.emit()
            self.accept()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._is_active:
            self._on_cancel()
            event.ignore()
        else:
            super().closeEvent(event)
