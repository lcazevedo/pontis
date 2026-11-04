# SPDX-License-Identifier: GPL-3.0-or-later
"""Watch and sync dialog: interactive real-time folder monitoring with watchdog."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pontis.i18n import tr
from pontis.services.watch_service import ProfileWatchError, WatchService
from pontis.ui.icons import get_icon
from pontis.ui.sync_worker import SyncWorker

if TYPE_CHECKING:
    from pontis.domain.models import RunResult, SyncProfile
    from pontis.infra.rclone_adapter import AdapterOutcome
    from pontis.services.run_service import RunService


class _WatchEventBridge(QObject):
    """Bridge for safely dispatching events from worker threads to the Qt GUI."""

    file_changed = Signal(str, str)
    sync_requested = Signal()


class WatchDialog(QDialog):
    """Dialog for monitoring folder changes and triggering syncs automatically."""

    def __init__(
        self,
        profile: SyncProfile,
        run_service: RunService,
        watch_service: WatchService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.run_service = run_service
        self.watch_service = watch_service if watch_service is not None else WatchService()
        self._owned_watch_service = watch_service is None

        self._bridge = _WatchEventBridge()
        self._bridge.file_changed.connect(self._on_file_changed)
        self._bridge.sync_requested.connect(self._on_sync_requested)

        self._worker: SyncWorker | None = None
        self._is_watching = False
        self._pending_sync_after_finish = False

        self.setWindowTitle(tr("ui.dialog.watch.title", name=self.profile.name))
        self.resize(700, 480)
        self.setWindowIcon(get_icon("system-search"))

        self._init_ui()
        self._check_watchable()

    def _init_ui(self) -> None:
        """Construct dialog widgets and layouts."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header info
        header_layout = QHBoxLayout()
        icon_label = QLabel(self)
        icon_label.setPixmap(get_icon("system-search").pixmap(36, 36))
        header_layout.addWidget(icon_label)

        info_layout = QVBoxLayout()
        title_label = QLabel(f"<b>{self.profile.name}</b>", self)
        self._desc_label = QLabel(tr("ui.dialog.watch.description"), self)
        self._desc_label.setWordWrap(True)
        info_layout.addWidget(title_label)
        info_layout.addWidget(self._desc_label)
        header_layout.addLayout(info_layout, 1)
        layout.addLayout(header_layout)

        # Form options
        form_layout = QFormLayout()

        # Watched paths
        watchable = WatchService.get_watchable_paths(self.profile)
        paths_str = (
            ", ".join(str(p) for p in watchable) if watchable else tr("ui.dialog.watch.none")
        )
        self._paths_display = QLabel(f"<code>{paths_str}</code>", self)
        self._paths_display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form_layout.addRow(tr("ui.dialog.watch.folder_label"), self._paths_display)

        # Debounce spinbox
        self._debounce_spin = QDoubleSpinBox(self)
        self._debounce_spin.setRange(0.5, 300.0)
        self._debounce_spin.setSingleStep(1.0)
        self._debounce_spin.setValue(5.0)
        self._debounce_spin.setSuffix(f" {tr('ui.dialog.watch.seconds')}")
        self._debounce_spin.setToolTip(tr("ui.dialog.watch.debounce_tooltip"))
        form_layout.addRow(tr("ui.dialog.watch.debounce_label"), self._debounce_spin)

        # Dry-run checkbox
        self._dry_run_check = QCheckBox(tr("ui.dialog.watch.dry_run_label"), self)
        self._dry_run_check.setToolTip(tr("ui.dialog.watch.dry_run_tooltip"))
        form_layout.addRow("", self._dry_run_check)

        # Status label
        self._status_label = QLabel(tr("ui.dialog.watch.status_idle"), self)
        self._status_label.setStyleSheet("font-weight: bold; color: gray;")
        form_layout.addRow(tr("ui.dialog.watch.status_label"), self._status_label)

        layout.addLayout(form_layout)

        # Log view
        log_header_layout = QHBoxLayout()
        log_title = QLabel(f"<b>{tr('ui.dialog.watch.events_log')}</b>", self)
        log_header_layout.addWidget(log_title)
        log_header_layout.addStretch()

        self._btn_clear_log = QPushButton(tr("ui.dialog.watch.clear_log"), self)
        self._btn_clear_log.clicked.connect(self._on_clear_log)
        log_header_layout.addWidget(self._btn_clear_log)
        layout.addLayout(log_header_layout)

        self._log_text = QTextEdit(self)
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet(
            "font-family: monospace; font-size: 11px; background-color: palette(base);"
        )
        layout.addWidget(self._log_text, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_toggle = QPushButton(
            get_icon("media-playback-start"), tr("ui.dialog.watch.start"), self
        )
        self._btn_toggle.clicked.connect(self._on_toggle_watch)
        btn_layout.addWidget(self._btn_toggle)

        self._btn_close = QPushButton(tr("ui.dialog.watch.close"), self)
        self._btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self._btn_close)

        layout.addLayout(btn_layout)

    def _check_watchable(self) -> None:
        """Verify if there are local folders available to observe."""
        watchable = WatchService.get_watchable_paths(self.profile)
        if not watchable:
            self._btn_toggle.setEnabled(False)
            self._append_log(tr("ui.dialog.watch.no_local_folder_warning"))

    def _append_log(self, text: str) -> None:
        """Append a timestamped line to the log window."""
        now = datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f"[{now}] {text}")

    def _on_clear_log(self) -> None:
        """Clear log contents."""
        self._log_text.clear()

    def _on_toggle_watch(self) -> None:
        """Start or stop the watchdog observer."""
        if self._is_watching:
            self._stop_watching()
        else:
            self._start_watching()

    def _start_watching(self) -> None:
        """Start the watchdog filesystem observer."""
        try:
            folders = self.watch_service.start_watching(
                self.profile,
                debounce_seconds=self._debounce_spin.value(),
                on_change=lambda etype, path: self._bridge.file_changed.emit(etype, path),
                on_sync_triggered=lambda p: self._bridge.sync_requested.emit(),
            )
        except ProfileWatchError as err:
            QMessageBox.warning(self, tr("ui.dialog.watch.title", name=self.profile.name), str(err))
            return
        except Exception as err:
            QMessageBox.critical(
                self, tr("ui.dialog.watch.title", name=self.profile.name), str(err)
            )
            return

        self._is_watching = True
        self._debounce_spin.setEnabled(False)
        self._dry_run_check.setEnabled(False)
        self._btn_toggle.setText(tr("ui.dialog.watch.stop"))
        self._btn_toggle.setIcon(get_icon("media-playback-stop"))
        self._status_label.setText(tr("ui.dialog.watch.status_watching"))
        self._status_label.setStyleSheet("font-weight: bold; color: green;")

        folder_names = ", ".join(f.name for f in folders)
        self._append_log(tr("ui.dialog.watch.started_log", folders=folder_names))

    def _stop_watching(self) -> None:
        """Stop the watchdog observer."""
        profile_key = self.profile.id if self.profile.id is not None else hash(self.profile.name)
        self.watch_service.stop_watching(profile_key)

        self._is_watching = False
        self._debounce_spin.setEnabled(True)
        self._dry_run_check.setEnabled(True)
        self._btn_toggle.setText(tr("ui.dialog.watch.start"))
        self._btn_toggle.setIcon(get_icon("media-playback-start"))
        self._status_label.setText(tr("ui.dialog.watch.status_idle"))
        self._status_label.setStyleSheet("font-weight: bold; color: gray;")

        self._append_log(tr("ui.dialog.watch.stopped_log"))

    def _on_file_changed(self, event_type: str, path: str) -> None:
        """Handle detected change in local directory."""
        self._append_log(tr("ui.dialog.watch.change_detected", type=event_type, path=path))

    def _on_sync_requested(self) -> None:
        """Handle trigger from debounce timer: run synchronization."""
        if self._worker is not None and self._worker.isRunning():
            self._pending_sync_after_finish = True
            self._append_log(tr("ui.dialog.watch.sync_queued_busy"))
            return

        is_dry = self._dry_run_check.isChecked()
        self._append_log(tr("ui.dialog.watch.sync_starting", mode="(dry-run)" if is_dry else ""))
        self._status_label.setText(tr("ui.dialog.watch.status_syncing"))
        self._status_label.setStyleSheet("font-weight: bold; color: blue;")

        self._worker = SyncWorker(
            profile=self.profile,
            run_service=self.run_service,
            dry_run=is_dry,
            parent=self,
        )
        self._worker.finished_signal.connect(self._on_sync_finished)
        self._worker.error_signal.connect(self._on_sync_error)
        self._worker.start()

    def _on_sync_finished(self, result: RunResult, outcome: AdapterOutcome | None) -> None:
        """Worker completed synchronization."""
        self._worker = None
        status = result.status.value if result else "finished"
        self._append_log(
            tr(
                "ui.dialog.watch.sync_finished",
                status=status,
                transferred=result.files_transferred if result else 0,
                deleted=result.files_deleted if result else 0,
            )
        )

        if self._is_watching:
            self._status_label.setText(tr("ui.dialog.watch.status_watching"))
            self._status_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self._status_label.setText(tr("ui.dialog.watch.status_idle"))
            self._status_label.setStyleSheet("font-weight: bold; color: gray;")

        if self._pending_sync_after_finish and self._is_watching:
            self._pending_sync_after_finish = False
            self._on_sync_requested()

    def _on_sync_error(self, err_msg: str) -> None:
        """Worker encountered an error."""
        self._worker = None
        self._append_log(tr("ui.dialog.watch.sync_error", error=err_msg))

        if self._is_watching:
            self._status_label.setText(tr("ui.dialog.watch.status_watching"))
            self._status_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self._status_label.setText(tr("ui.dialog.watch.status_idle"))
            self._status_label.setStyleSheet("font-weight: bold; color: gray;")

    def closeEvent(self, event: Any) -> None:
        """Stop watching and cleanup on close."""
        if self._is_watching:
            self._stop_watching()
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        if self._owned_watch_service:
            self.watch_service.stop_all()
        super().closeEvent(event)
