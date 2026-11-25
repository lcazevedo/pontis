# SPDX-License-Identifier: GPL-3.0-or-later
"""About Pontis dialog presenting version, license, rclone details, and project links."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pontis import __version__ as APP_VERSION
from pontis.i18n import tr
from pontis.infra.rclone import format_version, locate_rclone
from pontis.links import (
    GITHUB_SPONSORS_URL,
    GITHUB_URL,
    KOFI_URL,
)
from pontis.ui.icons import get_icon

if TYPE_CHECKING:
    from pathlib import Path


class AboutDialog(QDialog):
    """About dialog presenting system and application information."""

    def __init__(
        self,
        rclone_binary: Path | str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._rclone_binary = rclone_binary

        self.setWindowTitle(tr("ui.dialog.about.title"))
        self.setFixedSize(520, 430)
        self.setWindowIcon(get_icon("help-about"))
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header with Logo and Titles
        header_layout = QHBoxLayout()
        logo_label = QLabel(self)
        logo_label.setPixmap(get_icon("sync").pixmap(64, 64))
        header_layout.addWidget(logo_label)

        title_layout = QVBoxLayout()
        name_label = QLabel(f"<b>Pontis</b> v{APP_VERSION}", self)
        name_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        title_layout.addWidget(name_label)

        desc_label = QLabel(tr("ui.dialog.about.description"), self)
        desc_label.setWordWrap(True)
        title_layout.addWidget(desc_label)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # System & Rclone status info
        rclone_status = tr("ui.dialog.about.rclone_detecting")
        try:
            info = locate_rclone(self._rclone_binary)
            rclone_status = f"rclone v{format_version(info.version)} ({info.source}: {info.path})"
        except Exception:
            rclone_status = tr("ui.dialog.about.rclone_not_found")

        details_layout = QVBoxLayout()
        details_layout.setSpacing(4)

        rclone_label = QLabel(f"<b>rclone:</b> {rclone_status}", self)
        rclone_label.setWordWrap(True)
        details_layout.addWidget(rclone_label)

        license_label = QLabel(tr("ui.dialog.about.license_info"), self)
        license_label.setWordWrap(True)
        details_layout.addWidget(license_label)

        author_label = QLabel(tr("ui.dialog.about.author_info"), self)
        details_layout.addWidget(author_label)

        layout.addLayout(details_layout)

        # Discreet voluntary support section
        support_group = QGroupBox(tr("ui.dialog.about.support_title"), self)
        support_layout = QVBoxLayout(support_group)
        support_layout.setSpacing(8)

        support_text = QLabel(tr("ui.dialog.about.support_text"), self)
        support_text.setWordWrap(True)
        support_layout.addWidget(support_text)

        support_btns = QHBoxLayout()
        support_btns.setSpacing(8)
        self._support_sponsors_btn = self._make_support_button(
            "ui.support.github_sponsors", GITHUB_SPONSORS_URL
        )
        self._support_kofi_btn = self._make_support_button("ui.support.kofi", KOFI_URL)
        support_btns.addWidget(self._support_sponsors_btn)
        support_btns.addWidget(self._support_kofi_btn)
        support_btns.addStretch()
        support_layout.addLayout(support_btns)

        layout.addWidget(support_group)
        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()

        self._repo_button = QPushButton(tr("ui.dialog.about.github_button"), self)
        self._repo_button.setIcon(get_icon("emblem-web"))
        self._repo_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        btn_layout.addWidget(self._repo_button)

        btn_layout.addStretch()

        close_button = QPushButton(tr("ui.dialog.about.close"), self)
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        btn_layout.addWidget(close_button)

        layout.addLayout(btn_layout)

    def _make_support_button(self, label_key: str, url: str) -> QPushButton:
        """Create a discreet secondary button that opens a voluntary support URL."""
        label = tr(label_key)
        btn = QPushButton(label, self)
        btn.setObjectName("supportLinkButton")
        btn.setToolTip(url)
        btn.setAccessibleName(label)
        btn.clicked.connect(
            lambda _checked=False, target=url: QDesktopServices.openUrl(QUrl(target))
        )
        return btn
