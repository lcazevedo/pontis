# SPDX-License-Identifier: GPL-3.0-or-later
"""Reusable widget for configuring a sync endpoint (local directory or cloud remote)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from pontis.domain.models import Endpoint, EndpointKind
from pontis.i18n import tr
from pontis.services.remote_service import RemoteOperationError, RemoteService
from pontis.ui.icons import get_icon
from pontis.ui.widgets.cloud_browser_dialog import CloudFolderBrowserDialog


class EndpointPickerWidget(QWidget):
    """Interactive selector for a local folder or a cloud remote path."""

    changed = Signal()

    def __init__(
        self,
        remote_service: RemoteService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._remote_service = remote_service
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Kind Selection Group
        kind_layout = QHBoxLayout()
        self._rb_local = QRadioButton(tr("ui.endpoint.kind_local"), self)
        self._rb_remote = QRadioButton(tr("ui.endpoint.kind_remote"), self)
        self._rb_local.setChecked(True)

        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self._rb_local)
        self._btn_group.addButton(self._rb_remote)
        self._btn_group.buttonToggled.connect(self._on_kind_toggled)

        kind_layout.addWidget(self._rb_local)
        kind_layout.addWidget(self._rb_remote)
        kind_layout.addStretch()
        layout.addLayout(kind_layout)

        # Local Container Group
        self._local_box = QGroupBox(self)
        local_layout = QHBoxLayout(self._local_box)
        self._edit_local_path = QLineEdit(self)
        self._edit_local_path.setPlaceholderText("/home/user/Documents")
        self._edit_local_path.textChanged.connect(lambda: self.changed.emit())

        self._btn_browse_local = QPushButton(
            get_icon("folder"), tr("ui.endpoint.browse_local"), self
        )
        self._btn_browse_local.clicked.connect(self._on_browse_local)

        local_layout.addWidget(self._edit_local_path, 1)
        local_layout.addWidget(self._btn_browse_local)
        layout.addWidget(self._local_box)

        # Remote Container Group
        self._remote_box = QGroupBox(self)
        remote_layout = QFormLayout(self._remote_box)

        self._remote_combo = QComboBox(self)
        self._remote_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        remote_layout.addRow(tr("ui.endpoint.remote_name"), self._remote_combo)

        subfolder_layout = QHBoxLayout()
        self._edit_remote_path = QLineEdit(self)
        self._edit_remote_path.setPlaceholderText("(root or subfolder/path)")
        self._edit_remote_path.textChanged.connect(lambda: self.changed.emit())

        self._btn_browse_remote = QPushButton(
            get_icon("folder-remote"), tr("ui.endpoint.browse_remote"), self
        )
        self._btn_browse_remote.clicked.connect(self._on_browse_remote)

        subfolder_layout.addWidget(self._edit_remote_path, 1)
        subfolder_layout.addWidget(self._btn_browse_remote)
        remote_layout.addRow(tr("ui.endpoint.remote_path"), subfolder_layout)

        self._lbl_no_remotes = QLabel(tr("ui.endpoint.no_remotes"), self)
        self._lbl_no_remotes.setStyleSheet("color: #b91c1c; font-style: italic;")
        self._lbl_no_remotes.setVisible(False)
        remote_layout.addRow(self._lbl_no_remotes)

        layout.addWidget(self._remote_box)

        self._load_remotes()
        self._update_visibility()

    def _load_remotes(self) -> None:
        try:
            remotes = self._remote_service.list_remotes()
        except RemoteOperationError:
            remotes = []
        self._remote_combo.clear()
        for r in remotes:
            self._remote_combo.addItem(f"{r.name} ({r.type})", r.name)

        has_remotes = bool(remotes)
        self._remote_combo.setEnabled(has_remotes)
        self._edit_remote_path.setEnabled(has_remotes)
        self._btn_browse_remote.setEnabled(has_remotes)
        self._lbl_no_remotes.setVisible(not has_remotes)

    def _on_kind_toggled(self) -> None:
        self._update_visibility()
        self.changed.emit()

    def _update_visibility(self) -> None:
        is_local = self._rb_local.isChecked()
        self._local_box.setVisible(is_local)
        self._remote_box.setVisible(not is_local)

    def _on_browse_local(self) -> None:
        current = self._edit_local_path.text().strip()
        start_dir = current if current and Path(current).is_dir() else str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("ui.endpoint.dialog_select_local"),
            start_dir,
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self._edit_local_path.setText(folder)

    def _on_browse_remote(self) -> None:
        remote_data = self._remote_combo.currentData()
        remote_name = str(remote_data) if remote_data is not None else None
        current_path = self._edit_remote_path.text().strip()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._btn_browse_remote.setEnabled(False)
        try:
            dialog = CloudFolderBrowserDialog(
                remote_service=self._remote_service,
                initial_remote=remote_name,
                initial_path=current_path,
                parent=self,
            )
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

            if dialog.exec():
                selected_remote = dialog.selected_remote()
                selected_path = dialog.selected_path()
                idx = self._remote_combo.findData(selected_remote)
                if idx >= 0:
                    self._remote_combo.setCurrentIndex(idx)
                self._edit_remote_path.setText(selected_path)
        finally:
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            self._btn_browse_remote.setEnabled(True)

    def set_endpoint(self, endpoint: Endpoint) -> None:
        """Populate the widget controls from an existing Endpoint."""
        if endpoint.kind is EndpointKind.LOCAL:
            self._rb_local.setChecked(True)
            self._edit_local_path.setText(endpoint.path)
        else:
            self._rb_remote.setChecked(True)
            idx = self._remote_combo.findData(endpoint.remote)
            if idx >= 0:
                self._remote_combo.setCurrentIndex(idx)
            elif endpoint.remote:
                self._remote_combo.addItem(endpoint.remote, endpoint.remote)
                self._remote_combo.setCurrentIndex(self._remote_combo.count() - 1)
            self._edit_remote_path.setText(endpoint.path)
        self._update_visibility()

    def get_endpoint(self) -> Endpoint | None:
        """Construct an Endpoint from current values, or return None if invalid."""
        valid, _ = self.is_valid()
        if not valid:
            return None

        if self._rb_local.isChecked():
            return Endpoint.local(self._edit_local_path.text().strip())

        remote_data = self._remote_combo.currentData()
        remote_name = str(remote_data) if remote_data is not None else ""
        return Endpoint.cloud(remote_name, self._edit_remote_path.text().strip())

    def is_valid(self) -> tuple[bool, str]:
        """Validate current inputs. Returns (is_valid, error_message)."""
        if self._rb_local.isChecked():
            path = self._edit_local_path.text().strip()
            if not path:
                return False, tr("ui.endpoint.error_no_local_path")
            return True, ""

        remote_data = self._remote_combo.currentData()
        if not remote_data:
            return False, tr("ui.endpoint.error_no_remote")
        return True, ""
