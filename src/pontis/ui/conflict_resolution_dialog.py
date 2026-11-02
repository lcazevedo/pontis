# SPDX-License-Identifier: GPL-3.0-or-later
"""Conflict resolution dialog for conflicted file pairs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QGroupBox,
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

from pontis.i18n import tr
from pontis.services.conflict_service import (
    ConflictItem,
    ConflictResolution,
    ConflictService,
)
from pontis.ui.icons import get_icon

if TYPE_CHECKING:
    from pathlib import Path

    from pontis.domain.models import SyncProfile


def _format_size(size_bytes: int) -> str:
    """Format bytes into readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    kb = size_bytes / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    return f"{mb:.1f} MB"


class ConflictResolutionDialog(QDialog):
    """Dialog allowing users to inspect and resolve conflicted files."""

    sync_requested = Signal()

    def __init__(
        self,
        profile: SyncProfile,
        conflict_service: ConflictService | None = None,
        *,
        rclone_binary: Path | str = "rclone",
        rclone_config: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._service = (
            conflict_service
            if conflict_service is not None
            else ConflictService(rclone_binary=rclone_binary, config_path=rclone_config)
        )
        self._conflicts: list[ConflictItem] = []
        self._combos: dict[str, QComboBox] = {}
        self.should_sync_after: bool = False

        self.setWindowTitle(tr("ui.conflicts.title", name=profile.name))
        self.resize(950, 600)
        self.setWindowIcon(get_icon("emblem-important"))

        self._init_ui()
        self.load_conflicts()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header with description and refresh
        header_layout = QHBoxLayout()
        icon_lbl = QLabel(self)
        icon_lbl.setPixmap(get_icon("emblem-important").pixmap(28, 28))
        header_layout.addWidget(icon_lbl)

        info_layout = QVBoxLayout()
        title_lbl = QLabel(f"<b>{tr('ui.conflicts.title', name=self._profile.name)}</b>", self)
        subtitle_lbl = QLabel(tr("ui.conflicts.subtitle"), self)
        subtitle_lbl.setWordWrap(True)
        info_layout.addWidget(title_lbl)
        info_layout.addWidget(subtitle_lbl)
        header_layout.addLayout(info_layout, 1)

        self._btn_refresh = QPushButton(
            get_icon("view-refresh"), tr("ui.conflicts.btn_refresh"), self
        )
        self._btn_refresh.clicked.connect(self.load_conflicts)
        header_layout.addWidget(self._btn_refresh)
        layout.addLayout(header_layout)

        # Splitter: Table above, preview below
        splitter = QSplitter(Qt.Orientation.Vertical, self)

        # Table
        self._table = QTableWidget(self)
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            [
                tr("ui.conflicts.table.file"),
                tr("ui.conflicts.table.side_a"),
                tr("ui.conflicts.table.side_b"),
                tr("ui.conflicts.table.action"),
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self._table.itemSelectionChanged.connect(self._on_table_selection_changed)
        splitter.addWidget(self._table)

        # Preview area
        preview_widget = QWidget(self)
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 4, 0, 0)
        preview_layout.setSpacing(4)

        preview_header = QLabel(f"<b>{tr('ui.conflicts.preview.title')}</b>", self)
        preview_layout.addWidget(preview_header)

        preview_split = QSplitter(Qt.Orientation.Horizontal, preview_widget)

        # Side A preview
        title_a = f"{tr('ui.conflicts.preview.side_a')} {self._profile.side_a.to_rclone()}"
        box_a = QGroupBox(title_a, self)
        box_a_layout = QVBoxLayout(box_a)
        box_a_layout.setContentsMargins(4, 4, 4, 4)
        self._preview_a = QPlainTextEdit(self)
        self._preview_a.setReadOnly(True)
        self._set_mono_font(self._preview_a)
        box_a_layout.addWidget(self._preview_a)
        preview_split.addWidget(box_a)

        # Side B preview
        title_b = f"{tr('ui.conflicts.preview.side_b')} {self._profile.side_b.to_rclone()}"
        box_b = QGroupBox(title_b, self)
        box_b_layout = QVBoxLayout(box_b)
        box_b_layout.setContentsMargins(4, 4, 4, 4)
        self._preview_b = QPlainTextEdit(self)
        self._preview_b.setReadOnly(True)
        self._set_mono_font(self._preview_b)
        box_b_layout.addWidget(self._preview_b)
        preview_split.addWidget(box_b)

        preview_layout.addWidget(preview_split, 1)
        splitter.addWidget(preview_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        # Batch actions
        batch_layout = QHBoxLayout()
        batch_layout.setSpacing(6)
        batch_lbl = QLabel(tr("ui.conflicts.batch_label"), self)
        batch_layout.addWidget(batch_lbl)

        btn_all_a = QPushButton(tr("ui.conflicts.action.keep_side_a"), self)
        btn_all_a.clicked.connect(lambda: self._set_all_resolutions(ConflictResolution.KEEP_SIDE_A))
        batch_layout.addWidget(btn_all_a)

        btn_all_b = QPushButton(tr("ui.conflicts.action.keep_side_b"), self)
        btn_all_b.clicked.connect(lambda: self._set_all_resolutions(ConflictResolution.KEEP_SIDE_B))
        batch_layout.addWidget(btn_all_b)

        btn_all_both = QPushButton(tr("ui.conflicts.action.keep_both"), self)
        btn_all_both.clicked.connect(
            lambda: self._set_all_resolutions(ConflictResolution.KEEP_BOTH)
        )
        batch_layout.addWidget(btn_all_both)

        batch_layout.addStretch()
        layout.addLayout(batch_layout)

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        self._status_label = QLabel(self)
        bottom_layout.addWidget(self._status_label)
        bottom_layout.addStretch()

        self._btn_apply = QPushButton(tr("ui.conflicts.btn_apply"), self)
        self._btn_apply.setStyleSheet("font-weight: bold;")
        self._btn_apply.clicked.connect(self._on_apply)
        bottom_layout.addWidget(self._btn_apply)

        self._btn_close = QPushButton(tr("ui.conflicts.btn_close"), self)
        self._btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self._btn_close)
        layout.addLayout(bottom_layout)

    @staticmethod
    def _set_mono_font(widget: QPlainTextEdit) -> None:
        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        widget.setFont(font)

    def load_conflicts(self) -> None:
        """Scan profile for conflict files and update table."""
        self._conflicts = self._service.scan_conflicts(self._profile)
        self._combos.clear()
        self._table.setRowCount(len(self._conflicts))

        if not self._conflicts:
            self._table.setRowCount(0)
            self._status_label.setText(tr("ui.conflicts.no_conflicts"))
            self._status_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
            self._btn_apply.setEnabled(False)
            self._clear_previews()
            return

        self._btn_apply.setEnabled(True)
        self._status_label.setText(f"{len(self._conflicts)} conflict(s)")
        self._status_label.setStyleSheet("")

        for row, item in enumerate(self._conflicts):
            # 0: File name
            name_widget = QTableWidgetItem(item.base_name)
            name_widget.setData(Qt.ItemDataRole.UserRole, item)
            self._table.setItem(row, 0, name_widget)

            # 1: Side A
            a_str = "—"
            if item.side_a_file:
                sz = _format_size(item.side_a_file.size)
                dt = (
                    item.side_a_file.modified.strftime("%Y-%m-%d %H:%M")
                    if item.side_a_file.modified
                    else ""
                )
                a_str = f"{sz} ({dt})" if dt else sz
            self._table.setItem(row, 1, QTableWidgetItem(a_str))

            # 2: Side B
            b_str = "—"
            if item.side_b_file:
                sz = _format_size(item.side_b_file.size)
                dt = (
                    item.side_b_file.modified.strftime("%Y-%m-%d %H:%M")
                    if item.side_b_file.modified
                    else ""
                )
                b_str = f"{sz} ({dt})" if dt else sz
            self._table.setItem(row, 2, QTableWidgetItem(b_str))

            # 3: Action combo box
            combo = QComboBox(self)
            combo.addItem(tr("ui.conflicts.action.keep_side_a"), ConflictResolution.KEEP_SIDE_A)
            combo.addItem(tr("ui.conflicts.action.keep_side_b"), ConflictResolution.KEEP_SIDE_B)
            combo.addItem(tr("ui.conflicts.action.keep_both"), ConflictResolution.KEEP_BOTH)
            combo.addItem(tr("ui.conflicts.action.delete_both"), ConflictResolution.DELETE_BOTH)
            self._combos[item.base_name] = combo
            self._table.setCellWidget(row, 3, combo)

        self._table.selectRow(0)

    def _set_all_resolutions(self, action: ConflictResolution) -> None:
        """Batch set all combo boxes to the given resolution action."""
        for combo in self._combos.values():
            idx = combo.findData(action)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _on_table_selection_changed(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            self._clear_previews()
            return
        row = selected_rows[0].row()
        item = self._table.item(row, 0)
        if item is None:
            self._clear_previews()
            return
        conflict = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(conflict, ConflictItem):
            self._clear_previews()
            return

        text_a = conflict.side_a_file.preview if conflict.side_a_file else ""
        text_b = conflict.side_b_file.preview if conflict.side_b_file else ""

        self._preview_a.setPlainText(text_a or tr("ui.conflicts.preview.not_available"))
        self._preview_b.setPlainText(text_b or tr("ui.conflicts.preview.not_available"))

    def _clear_previews(self) -> None:
        self._preview_a.setPlainText("")
        self._preview_b.setPlainText("")

    def _on_apply(self) -> None:
        resolutions: dict[str, ConflictResolution] = {}
        for base_name, combo in self._combos.items():
            action = combo.currentData()
            if action:
                resolutions[base_name] = ConflictResolution(str(action))

        if not resolutions:
            return

        results = self._service.resolve_all(self._profile, resolutions)
        resolved_count = sum(1 for v in results.values() if v)

        msg = tr("ui.conflicts.applied_msg", count=resolved_count)
        reply = QMessageBox.information(
            self,
            tr("ui.conflicts.title", name=self._profile.name),
            f"{msg}\n\n{tr('ui.conflicts.btn_sync_now')}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        self.load_conflicts()
        if reply == QMessageBox.StandardButton.Yes:
            self.should_sync_after = True
            self.sync_requested.emit()
            self.accept()
