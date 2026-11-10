# SPDX-License-Identifier: GPL-3.0-or-later
"""Update dialog displaying release information, release notes, and download links."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pontis.i18n import tr
from pontis.ui.icons import get_icon

if TYPE_CHECKING:
    from pontis.services.update_service import UpdateInfo


class UpdateDialog(QDialog):
    """Dialog notifying the user about new releases or confirming latest version."""

    def __init__(
        self,
        info: UpdateInfo,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._info = info
        self._ignore_requested = False

        self.setWindowTitle(
            tr("ui.dialog.update.title_update")
            if info.has_update
            else tr("ui.dialog.update.title_latest")
        )
        self.setMinimumSize(540, 420)
        self.setWindowIcon(get_icon("system-software-update"))
        self._init_ui()

    @property
    def ignore_requested(self) -> bool:
        """Return True if the user checked 'Ignore this version'."""
        return self._ignore_requested

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header with icon and status text
        header_layout = QHBoxLayout()
        icon_label = QLabel(self)
        icon_label.setPixmap(
            get_icon("system-software-update").pixmap(48, 48)
            if self._info.has_update
            else get_icon("emblem-default").pixmap(48, 48)
        )
        header_layout.addWidget(icon_label)

        status_layout = QVBoxLayout()
        if self._info.has_update:
            title_text = f"<b>{tr('ui.dialog.update.available_header')}</b>"
            subtitle_text = tr(
                "ui.dialog.update.versions_compare",
                latest=self._info.latest_version,
                current=self._info.current_version,
            )
        else:
            title_text = f"<b>{tr('ui.dialog.update.latest_header')}</b>"
            subtitle_text = tr(
                "ui.dialog.update.latest_desc",
                current=self._info.current_version,
            )

        title_label = QLabel(title_text, self)
        title_label.setStyleSheet("font-size: 14pt;")
        status_layout.addWidget(title_label)

        sub_label = QLabel(subtitle_text, self)
        sub_label.setWordWrap(True)
        status_layout.addWidget(sub_label)

        if self._info.published_at:
            pub_date = self._info.published_at[:10]
            date_label = QLabel(tr("ui.dialog.update.published_date", date=pub_date), self)
            date_label.setStyleSheet("color: #64748b; font-size: 9pt;")
            status_layout.addWidget(date_label)

        header_layout.addLayout(status_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Release notes text browser (if update available)
        if self._info.has_update and self._info.release_notes:
            notes_header = QLabel(f"<b>{tr('ui.dialog.update.notes_title')}</b>", self)
            layout.addWidget(notes_header)

            self._notes_browser = QTextBrowser(self)
            self._notes_browser.setPlainText(self._info.release_notes)
            self._notes_browser.setAccessibleName(tr("ui.dialog.update.notes_title"))
            layout.addWidget(self._notes_browser, 1)

        # Ignore version checkbox
        if self._info.has_update:
            self._ignore_checkbox = QCheckBox(
                tr("ui.dialog.update.ignore_version", version=self._info.latest_version),
                self,
            )
            layout.addWidget(self._ignore_checkbox)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if self._info.has_update:
            self._open_button = QPushButton(tr("ui.dialog.update.open_download"), self)
            self._open_button.setDefault(True)
            self._open_button.setIcon(get_icon("document-open"))
            self._open_button.clicked.connect(self._on_open_download)
            btn_layout.addWidget(self._open_button)

            self._close_button = QPushButton(tr("ui.dialog.update.later"), self)
            self._close_button.clicked.connect(self._on_close)
            btn_layout.addWidget(self._close_button)
        else:
            self._close_button = QPushButton(tr("ui.dialog.update.ok"), self)
            self._close_button.setDefault(True)
            self._close_button.clicked.connect(self.accept)
            btn_layout.addWidget(self._close_button)

        layout.addLayout(btn_layout)

    def _on_open_download(self) -> None:
        if self._info.release_url:
            QDesktopServices.openUrl(QUrl(self._info.release_url))
        self._on_close()

    def _on_close(self) -> None:
        if hasattr(self, "_ignore_checkbox") and self._ignore_checkbox.isChecked():
            self._ignore_requested = True
        self.accept()
