# SPDX-License-Identifier: GPL-3.0-or-later
"""Execution history and log viewer dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pontis.domain.models import RunResult, RunStatus
from pontis.i18n import tr
from pontis.ui.icons import get_icon

if TYPE_CHECKING:
    from pathlib import Path

    from pontis.services.profile_service import ProfileService


class HistoryDialog(QDialog):
    """Dialog displaying execution runs, metrics and logs."""

    def __init__(
        self,
        service: ProfileService,
        *,
        initial_profile_id: int | None = None,
        log_dir: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._initial_profile_id = initial_profile_id
        self._log_dir = log_dir
        self._all_runs: list[RunResult] = []
        self._profiles_by_id = {p.id: p for p in self._service.list_profiles() if p.id is not None}

        self.setWindowTitle(tr("ui.history.title"))
        self.resize(950, 600)
        self.setWindowIcon(get_icon("document-open-recent"))

        self._init_ui()
        self._populate_filters()
        self.load_history()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        # Profile filter
        lbl_profile = QLabel(tr("ui.history.table.profile"), self)
        self._combo_profile = QComboBox(self)
        self._combo_profile.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(lbl_profile)
        filter_layout.addWidget(self._combo_profile)

        # Status filter
        lbl_status = QLabel(tr("ui.history.table.status"), self)
        self._combo_status = QComboBox(self)
        self._combo_status.addItem(tr("ui.history.filter_status_all"), "all")
        self._combo_status.addItem(tr("ui.history.filter_status_success"), "success")
        self._combo_status.addItem(tr("ui.history.filter_status_error"), "error")
        self._combo_status.addItem(tr("ui.history.filter_status_cancelled"), "cancelled")
        self._combo_status.addItem(tr("ui.history.filter_status_dry"), "dry_run")
        self._combo_status.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(lbl_status)
        filter_layout.addWidget(self._combo_status)

        # Refresh button
        self._btn_refresh = QPushButton(get_icon("view-refresh"), "", self)
        self._btn_refresh.setToolTip(tr("ui.actions.refresh"))
        self._btn_refresh.clicked.connect(self.load_history)
        filter_layout.addWidget(self._btn_refresh)

        filter_layout.addStretch()

        # Clear history button
        self._btn_clear = QPushButton(get_icon("edit-clear"), tr("ui.history.btn_clear"), self)
        self._btn_clear.clicked.connect(self._on_clear_history)
        filter_layout.addWidget(self._btn_clear)

        layout.addLayout(filter_layout)

        # Splitter: Table on left, Details on right
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left pane: Runs Table
        self._table = QTableWidget(self)
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            [
                tr("ui.history.table.id"),
                tr("ui.history.table.profile"),
                tr("ui.history.table.started"),
                tr("ui.history.table.duration"),
                tr("ui.history.table.mode"),
                tr("ui.history.table.status"),
                tr("ui.history.table.files"),
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self._table.itemSelectionChanged.connect(self._on_run_selected)
        splitter.addWidget(self._table)

        # Right pane: Details & Log Viewer
        details_widget = QWidget(self)
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(4, 0, 0, 0)
        details_layout.setSpacing(8)

        # Summary box
        self._summary_frame = QFrame(self)
        self._summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        summary_inner = QVBoxLayout(self._summary_frame)
        summary_inner.setContentsMargins(8, 8, 8, 8)
        summary_inner.setSpacing(4)

        self._lbl_details_title = QLabel(f"<b>{tr('ui.history.details.title')}</b>", self)
        self._lbl_details_meta = QLabel(tr("ui.history.details.none_selected"), self)
        self._lbl_details_meta.setWordWrap(True)
        summary_inner.addWidget(self._lbl_details_title)
        summary_inner.addWidget(self._lbl_details_meta)
        details_layout.addWidget(self._summary_frame)

        # Log editor
        self._log_edit = QPlainTextEdit(self)
        self._log_edit.setReadOnly(True)
        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self._log_edit.setFont(font)
        details_layout.addWidget(self._log_edit, 1)

        # Details action buttons
        actions_layout = QHBoxLayout()
        self._btn_export = QPushButton(get_icon("document-save"), tr("ui.history.btn_export"), self)
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._on_export_log)
        actions_layout.addWidget(self._btn_export)

        self._btn_copy = QPushButton(get_icon("edit-copy"), tr("ui.history.btn_copy"), self)
        self._btn_copy.setEnabled(False)
        self._btn_copy.clicked.connect(self._on_copy_log)
        actions_layout.addWidget(self._btn_copy)

        actions_layout.addStretch()
        details_layout.addLayout(actions_layout)

        splitter.addWidget(details_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        # Bottom Close button
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self._btn_close = QPushButton(tr("ui.history.btn_close"), self)
        self._btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self._btn_close)
        layout.addLayout(bottom_layout)

    def _populate_filters(self) -> None:
        """Populate profile selector with 'All Profiles' and configured profiles."""
        self._combo_profile.blockSignals(True)
        self._combo_profile.clear()
        self._combo_profile.addItem(tr("ui.history.filter_all_profiles"), None)

        select_index = 0
        idx = 1
        for pid, profile in sorted(self._profiles_by_id.items(), key=lambda x: x[1].name.lower()):
            self._combo_profile.addItem(profile.name, pid)
            if self._initial_profile_id is not None and pid == self._initial_profile_id:
                select_index = idx
            idx += 1

        self._combo_profile.setCurrentIndex(select_index)
        self._combo_profile.blockSignals(False)

    def _on_filter_changed(self) -> None:
        """Re-filter displayed runs when combo boxes change."""
        self._apply_filter()

    def load_history(self) -> None:
        """Fetch all runs from SQLite and populate the table."""
        self._all_runs = self._service.list_runs()
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Filter self._all_runs and rebuild table rows."""
        selected_pid = self._combo_profile.currentData()
        status_filter = self._combo_status.currentData()

        filtered: list[RunResult] = []
        for run in self._all_runs:
            if selected_pid is not None and run.profile_id != selected_pid:
                continue
            if status_filter == "success" and run.status != RunStatus.SUCCESS:
                continue
            if status_filter == "error" and run.status != RunStatus.ERROR:
                continue
            if status_filter == "cancelled" and run.status != RunStatus.CANCELLED:
                continue
            if status_filter == "dry_run" and not run.dry_run:
                continue
            filtered.append(run)

        self._table.setRowCount(len(filtered))
        for row, r in enumerate(filtered):
            pname = (
                self._profiles_by_id[r.profile_id].name
                if r.profile_id in self._profiles_by_id
                else f"#{r.profile_id}"
            )

            # 0: ID
            item_id = QTableWidgetItem(str(r.id))
            item_id.setData(Qt.ItemDataRole.UserRole, r)
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, item_id)

            # 1: Profile
            self._table.setItem(row, 1, QTableWidgetItem(pname))

            # 2: Date / Time
            started_str = r.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            self._table.setItem(row, 2, QTableWidgetItem(started_str))

            # 3: Duration
            duration_str = "—"
            if r.finished_at:
                secs = int((r.finished_at - r.started_at).total_seconds())
                mins, s = divmod(secs, 60)
                duration_str = f"{mins}m {s}s" if mins > 0 else f"{s}s"
            item_dur = QTableWidgetItem(duration_str)
            item_dur.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, item_dur)

            # 4: Mode
            mode_str = (
                tr("ui.history.table.mode_dry") if r.dry_run else tr("ui.history.table.mode_real")
            )
            item_mode = QTableWidgetItem(mode_str)
            item_mode.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 4, item_mode)

            # 5: Status
            status_item = self._format_status_item(r)
            self._table.setItem(row, 5, status_item)

            # 6: Files summary
            files_str = f"↑ {r.files_transferred}   ✗ {r.files_deleted}   ! {r.errors}"
            self._table.setItem(row, 6, QTableWidgetItem(files_str))

        if filtered:
            self._table.selectRow(0)
            self._on_run_selected()
        else:
            self._show_empty_details()

    def _format_status_item(self, r: RunResult) -> QTableWidgetItem:
        if r.status == RunStatus.SUCCESS:
            item = QTableWidgetItem(get_icon("status_success"), tr("ui.status.success"))
        elif r.status == RunStatus.ERROR:
            item = QTableWidgetItem(get_icon("status_error"), tr("ui.status.error"))
        elif r.status == RunStatus.CANCELLED:
            item = QTableWidgetItem(get_icon("status_cancelled"), tr("ui.status.cancelled"))
        else:
            item = QTableWidgetItem(get_icon("status_running"), tr("ui.status.running"))
        return item

    def _selected_run(self) -> RunResult | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        item = self._table.item(row, 0)
        if item is not None:
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, RunResult):
                return data
        return None

    def _on_run_selected(self) -> None:
        run = self._selected_run()
        if run is None or run.id is None:
            self._show_empty_details()
            return

        pname = (
            self._profiles_by_id[run.profile_id].name
            if run.profile_id in self._profiles_by_id
            else f"#{run.profile_id}"
        )
        started_str = run.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        finished_str = (
            run.finished_at.astimezone().strftime("%Y-%m-%d %H:%M:%S") if run.finished_at else "—"
        )
        duration_str = "—"
        if run.finished_at:
            secs = int((run.finished_at - run.started_at).total_seconds())
            mins, s = divmod(secs, 60)
            duration_str = f"{mins}m {s}s" if mins > 0 else f"{s}s"

        mode_tag = "Simulation (Dry Run)" if run.dry_run else "Real Sync"
        meta_lines = [
            f"<b>{pname}</b> — Run #{run.id} ({started_str})",
            f"Status: <b>{run.status.value.upper()}</b> | Mode: {mode_tag}",
            f"Finished: {finished_str} (Duration: {duration_str})",
            (
                f"Transferred: {run.files_transferred} | "
                f"Deleted: {run.files_deleted} | Errors: {run.errors}"
            ),
        ]
        if run.message:
            meta_lines.append(f"Message: {run.message}")

        self._lbl_details_meta.setText("<br>".join(meta_lines))

        # Load log content
        log_content = self._service.get_run_log(run.id, log_dir=self._log_dir)
        if not log_content.strip():
            log_content = tr("ui.history.details.empty_log")
        self._log_edit.setPlainText(log_content)

        self._btn_export.setEnabled(True)
        self._btn_copy.setEnabled(True)

    def _show_empty_details(self) -> None:
        self._lbl_details_meta.setText(tr("ui.history.details.none_selected"))
        self._log_edit.setPlainText("")
        self._btn_export.setEnabled(False)
        self._btn_copy.setEnabled(False)

    def _on_copy_log(self) -> None:
        text = self._log_edit.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)

    def _on_export_log(self) -> None:
        run = self._selected_run()
        if run is None or run.id is None:
            return

        default_name = f"pontis_run_{run.id}.log"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("ui.history.export_dialog_title"),
            default_name,
            "Log Files (*.log *.txt);;All Files (*)",
        )
        if not file_path:
            return

        try:
            from pathlib import Path

            self._service.export_run_log(run.id, Path(file_path), log_dir=self._log_dir)
            QMessageBox.information(
                self,
                tr("ui.history.title"),
                tr("ui.history.export_success", path=file_path),
            )
        except Exception as exc:
            QMessageBox.warning(self, tr("ui.history.title"), str(exc))

    def _on_clear_history(self) -> None:
        reply = QMessageBox.question(
            self,
            tr("ui.history.clear_confirm_title"),
            tr("ui.history.clear_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        selected_pid = self._combo_profile.currentData()
        if selected_pid is not None:
            self._service.delete_runs_for_profile(selected_pid)
        else:
            self._service.clear_all_runs()

        self.load_history()
