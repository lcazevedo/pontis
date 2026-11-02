# SPDX-License-Identifier: GPL-3.0-or-later
"""Dialog for browsing folders in cloud storage remotes using rclone."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pontis.i18n import tr
from pontis.services.remote_service import RemoteOperationError, RemoteService
from pontis.ui.icons import get_icon

if TYPE_CHECKING:
    pass


class CloudFolderBrowserDialog(QDialog):
    """Dialog allowing users to inspect and select directories inside a cloud remote."""

    def __init__(
        self,
        remote_service: RemoteService,
        initial_remote: str | None = None,
        initial_path: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._remote_service = remote_service
        self._current_path = initial_path.strip().strip("/")
        self._selected_path = self._current_path

        self.setWindowTitle(tr("ui.cloud_browser.title"))
        self.resize(540, 440)
        self.setWindowIcon(get_icon("folder-remote"))

        self._init_ui(initial_remote)
        self._load_remotes(initial_remote)

    def _init_ui(self, initial_remote: str | None) -> None:
        layout = QVBoxLayout(self)

        # Top row: Remote selector
        remote_layout = QHBoxLayout()
        remote_label = QLabel(tr("ui.cloud_browser.remote"), self)
        self._remote_combo = QComboBox(self)
        self._remote_combo.currentIndexChanged.connect(self._on_remote_changed)
        remote_layout.addWidget(remote_label)
        remote_layout.addWidget(self._remote_combo, 1)
        layout.addLayout(remote_layout)

        # Navigation row: Path bar, Up button, Refresh button, New Folder button
        nav_layout = QHBoxLayout()
        self._path_edit = QLineEdit(self)
        self._path_edit.setText(self._current_path)
        self._path_edit.returnPressed.connect(self._on_path_entered)

        self._btn_up = QPushButton(get_icon("go-up"), tr("ui.cloud_browser.up"), self)
        self._btn_up.clicked.connect(self._on_up_clicked)

        self._btn_refresh = QPushButton(
            get_icon("view-refresh"), tr("ui.cloud_browser.refresh"), self
        )
        self._btn_refresh.clicked.connect(self._refresh_folders)

        self._btn_new_folder = QPushButton(
            get_icon("folder-new"), tr("ui.cloud_browser.new_folder"), self
        )
        self._btn_new_folder.clicked.connect(self._on_new_folder_clicked)

        nav_layout.addWidget(QLabel(tr("ui.cloud_browser.path"), self))
        nav_layout.addWidget(self._path_edit, 1)
        nav_layout.addWidget(self._btn_up)
        nav_layout.addWidget(self._btn_refresh)
        nav_layout.addWidget(self._btn_new_folder)
        layout.addLayout(nav_layout)

        # Status / Loading indicator banner
        self._lbl_status = QLabel(self)
        self._lbl_status.setStyleSheet(
            "QLabel { background-color: #e0f2fe; color: #0369a1; "
            "padding: 6px; border-radius: 4px; font-weight: bold; font-size: 11px; }"
        )
        self._lbl_status.setVisible(False)
        layout.addWidget(self._lbl_status)

        # Folder list
        self._folder_list = QListWidget(self)
        self._folder_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._folder_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._folder_list, 1)

        # Current selection display
        self._lbl_selection = QLabel(self)
        self._update_selection_label()
        layout.addWidget(self._lbl_selection)

        # Dialog Buttons
        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._btn_box.button(QDialogButtonBox.StandardButton.Ok).setText(
            tr("ui.cloud_browser.select_current")
        )
        self._btn_box.accepted.connect(self.accept)
        self._btn_box.rejected.connect(self.reject)
        layout.addWidget(self._btn_box)

    def _load_remotes(self, initial_remote: str | None) -> None:
        try:
            remotes = self._remote_service.list_remotes()
        except RemoteOperationError:
            remotes = []
        self._remote_combo.blockSignals(True)
        self._remote_combo.clear()
        target_index = 0
        for idx, r in enumerate(remotes):
            self._remote_combo.addItem(f"{r.name} ({r.type})", r.name)
            if initial_remote and r.name == initial_remote:
                target_index = idx

        if remotes:
            self._remote_combo.setCurrentIndex(target_index)
            self._remote_combo.blockSignals(False)
            self._refresh_folders()
        else:
            self._remote_combo.blockSignals(False)
            self._folder_list.clear()
            item = QListWidgetItem(tr("ui.endpoint.no_remotes"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._folder_list.addItem(item)
            self._btn_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _on_remote_changed(self) -> None:
        self._current_path = ""
        self._selected_path = ""
        self._path_edit.setText("")
        self._refresh_folders()

    def _on_path_entered(self) -> None:
        self._current_path = self._path_edit.text().strip().strip("/")
        self._selected_path = self._current_path
        self._refresh_folders()

    def _on_up_clicked(self) -> None:
        if not self._current_path:
            return
        parts = self._current_path.split("/")
        self._current_path = "/".join(parts[:-1]) if len(parts) > 1 else ""
        self._selected_path = self._current_path
        self._path_edit.setText(self._current_path)
        self._refresh_folders()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        folder_name = item.data(Qt.ItemDataRole.UserRole)
        if not folder_name:
            return
        if self._current_path:
            self._current_path = f"{self._current_path}/{folder_name}"
        else:
            self._current_path = folder_name
        self._selected_path = self._current_path
        self._path_edit.setText(self._current_path)
        self._refresh_folders()

    def _on_selection_changed(self) -> None:
        selected_items = self._folder_list.selectedItems()
        if selected_items and selected_items[0].data(Qt.ItemDataRole.UserRole):
            folder_name = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if self._current_path:
                self._selected_path = f"{self._current_path}/{folder_name}"
            else:
                self._selected_path = folder_name
        else:
            self._selected_path = self._current_path
        self._update_selection_label()

    def _update_selection_label(self) -> None:
        remote = self.selected_remote()
        if self._selected_path:
            display = f"{remote}:{self._selected_path}"
        else:
            display = f"{remote}:/ {tr('ui.cloud_browser.root')}"
        self._lbl_selection.setText(display)

    def _on_new_folder_clicked(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            tr("ui.cloud_browser.new_folder_title"),
            tr("ui.cloud_browser.new_folder_prompt"),
        )
        if ok and name.strip():
            clean_name = name.strip().strip("/")
            new_path = f"{self._current_path}/{clean_name}" if self._current_path else clean_name
            self._current_path = new_path
            self._selected_path = new_path
            self._path_edit.setText(new_path)
            self._refresh_folders()

    def _refresh_folders(self) -> None:
        remote = self.selected_remote()
        if not remote:
            return

        self._folder_list.clear()
        self._btn_up.setEnabled(False)
        self._btn_refresh.setEnabled(False)
        self._btn_new_folder.setEnabled(False)
        self._path_edit.setEnabled(False)
        self._remote_combo.setEnabled(False)
        ok_btn = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setEnabled(False)

        # Show visual loading banner and item
        msg = tr("ui.cloud_browser.loading")
        self._lbl_status.setText(f"⏳ {msg}")
        self._lbl_status.setVisible(True)

        loading_item = QListWidgetItem(get_icon("view-refresh"), msg)
        loading_item.setFlags(Qt.ItemFlag.NoItemFlags)
        self._folder_list.addItem(loading_item)
        self._update_selection_label()

        # Set wait cursor and force immediate repaint so user sees feedback instantly
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

        try:
            dirs = self._remote_service.list_directories(remote, self._current_path)
            self._folder_list.clear()
            if not dirs:
                empty_item = QListWidgetItem(tr("ui.cloud_browser.empty"))
                empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
                self._folder_list.addItem(empty_item)
            else:
                for directory in dirs:
                    item = QListWidgetItem(get_icon("folder"), directory)
                    item.setData(Qt.ItemDataRole.UserRole, directory)
                    self._folder_list.addItem(item)
        except RemoteOperationError as exc:
            self._folder_list.clear()
            err_item = QListWidgetItem(tr("ui.cloud_browser.error", error=str(exc)))
            err_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._folder_list.addItem(err_item)
        finally:
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            self._lbl_status.setVisible(False)
            self._btn_up.setEnabled(bool(self._current_path))
            self._btn_refresh.setEnabled(True)
            self._btn_new_folder.setEnabled(True)
            self._path_edit.setEnabled(True)
            self._remote_combo.setEnabled(True)
            if ok_btn:
                ok_btn.setEnabled(True)

    def selected_remote(self) -> str:
        """Return the selected remote name."""
        data = self._remote_combo.currentData()
        return str(data) if data is not None else ""

    def selected_path(self) -> str:
        """Return the selected path inside the remote."""
        return self._selected_path

    def closeEvent(self, event: QCloseEvent) -> None:
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        super().closeEvent(event)

    def reject(self) -> None:
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        super().reject()
