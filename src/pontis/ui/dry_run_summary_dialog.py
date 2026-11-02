# SPDX-License-Identifier: GPL-3.0-or-later
"""Dialog summarizing planned changes from a dry-run simulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pontis.i18n import tr
from pontis.ui.icons import get_icon

if TYPE_CHECKING:
    from pontis.domain.models import SyncProfile
    from pontis.infra.rclone_adapter import AdapterOutcome


class DryRunSummaryDialog(QDialog):
    """Presents planned copies and deletions after a dry run."""

    def __init__(
        self,
        profile: SyncProfile,
        outcome: AdapterOutcome | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._outcome = outcome
        self._should_apply_sync = False
        self._apply_with_force = False

        self.setWindowTitle(tr("ui.dry_run.title", name=profile.name))
        self.resize(650, 480)
        self.setWindowIcon(get_icon("dialog-information"))

        self._init_ui()

    @property
    def should_apply_sync(self) -> bool:
        """True if the user chose to proceed with the real synchronization."""
        return self._should_apply_sync

    @property
    def apply_with_force(self) -> bool:
        """True if the synchronization should proceed with --force (user confirmed deletions)."""
        return self._apply_with_force

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header info
        header_box = QHBoxLayout()
        icon_lbl = QLabel(self)
        icon_lbl.setPixmap(get_icon("dialog-information").pixmap(32, 32))
        header_box.addWidget(icon_lbl)

        text_layout = QVBoxLayout()
        title_lbl = QLabel(f"<b>{tr('ui.dry_run.title', name=self._profile.name)}</b>", self)
        title_lbl.setStyleSheet("font-size: 14px;")
        sub_lbl = QLabel(tr("ui.dry_run.subtitle"), self)
        sub_lbl.setStyleSheet("color: gray;")
        sub_lbl.setWordWrap(True)
        text_layout.addWidget(title_lbl)
        text_layout.addWidget(sub_lbl)
        header_box.addLayout(text_layout)
        header_box.addStretch()
        layout.addLayout(header_box)

        # Tabs for copies and deletes
        tabs = QTabWidget(self)

        copies = self._outcome.planned_copy_files if self._outcome else []
        deletes = self._outcome.planned_delete_files if self._outcome else []

        # Tab 1: Copies
        tab_copies = QWidget(self)
        copies_layout = QVBoxLayout(tab_copies)
        self._copies_list = QListWidget(tab_copies)
        if copies:
            for item in copies:
                self._copies_list.addItem(item)
        else:
            self._copies_list.addItem(tr("ui.dry_run.empty_copies"))
        copies_layout.addWidget(self._copies_list)
        tabs.addTab(tab_copies, tr("ui.dry_run.tab_copies", count=len(copies)))

        # Tab 2: Deletes
        tab_deletes = QWidget(self)
        deletes_layout = QVBoxLayout(tab_deletes)
        self._deletes_list = QListWidget(tab_deletes)
        if deletes:
            for item in deletes:
                self._deletes_list.addItem(item)
        else:
            self._deletes_list.addItem(tr("ui.dry_run.empty_deletes"))
        deletes_layout.addWidget(self._deletes_list)
        tabs.addTab(tab_deletes, tr("ui.dry_run.tab_deletes", count=len(deletes)))

        layout.addWidget(tabs)

        # Mass delete warning & confirmation if there are deletes
        self._confirm_check: QCheckBox | None = None
        if deletes:
            warn_frame = QFrame(self)
            warn_frame.setFrameShape(QFrame.Shape.StyledPanel)
            warn_frame.setStyleSheet(
                "QFrame { background-color: rgba(245, 124, 0, 0.12); "
                "border: 1px solid #f57c00; border-radius: 4px; padding: 6px; }"
            )
            warn_layout = QVBoxLayout(warn_frame)

            warn_header = QHBoxLayout()
            warn_icon = QLabel(self)
            warn_icon.setPixmap(get_icon("dialog-warning").pixmap(22, 22))
            warn_header.addWidget(warn_icon)
            warn_msg = QLabel(
                f"<b>{tr('ui.dry_run.mass_delete_warning', count=len(deletes))}</b>", self
            )
            warn_msg.setStyleSheet("color: #d84315;")
            warn_header.addWidget(warn_msg)
            warn_header.addStretch()
            warn_layout.addLayout(warn_header)

            self._confirm_check = QCheckBox(tr("ui.dry_run.mass_delete_confirm"), self)
            self._confirm_check.toggled.connect(self._on_confirm_toggled)
            warn_layout.addWidget(self._confirm_check)

            layout.addWidget(warn_frame)

        # Buttons
        btn_box = QDialogButtonBox(self)
        self._btn_apply = QPushButton(get_icon("media-playback-start"), tr("ui.dry_run.btn_apply"))
        self._btn_apply.setStyleSheet("font-weight: bold;")
        self._btn_cancel = QPushButton(tr("ui.dry_run.btn_cancel"))

        btn_box.addButton(self._btn_apply, QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton(self._btn_cancel, QDialogButtonBox.ButtonRole.RejectRole)

        self._btn_apply.clicked.connect(self._on_apply)
        self._btn_cancel.clicked.connect(self.reject)

        if deletes:
            self._btn_apply.setEnabled(False)

        layout.addWidget(btn_box)

    def _on_confirm_toggled(self, checked: bool) -> None:
        self._btn_apply.setEnabled(checked)

    def _on_apply(self) -> None:
        self._should_apply_sync = True
        deletes = self._outcome.planned_delete_files if self._outcome else []
        if deletes:
            self._apply_with_force = True
        self.accept()
