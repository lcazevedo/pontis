# SPDX-License-Identifier: GPL-3.0-or-later
"""Empty state widget shown when no sync profiles exist."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pontis.i18n import tr
from pontis.ui.icons import get_icon


class EmptyStateWidget(QWidget):
    """Placeholder view explaining that no sync profiles are configured."""

    create_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)

        # Icon / Illustration
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setPixmap(get_icon("sync").pixmap(64, 64))
        layout.addWidget(self._icon_label)

        # Title
        self._title_label = QLabel(tr("ui.empty.title"))
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = self._title_label.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        layout.addWidget(self._title_label)

        # Subtitle
        self._subtitle_label = QLabel(tr("ui.empty.subtitle"))
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setStyleSheet("color: #64748b;")
        layout.addWidget(self._subtitle_label)

        # Action Button container
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._create_btn = QPushButton(tr("ui.empty.action_button"))
        self._create_btn.setIcon(get_icon("list-add"))
        self._create_btn.clicked.connect(self.create_requested.emit)
        btn_layout.addWidget(self._create_btn)
        layout.addLayout(btn_layout)

        # CLI Hint
        self._hint_label = QLabel(tr("ui.empty.cli_hint"))
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self._hint_label)

    def retranslate_ui(self) -> None:
        """Update strings after a language change."""
        self._title_label.setText(tr("ui.empty.title"))
        self._subtitle_label.setText(tr("ui.empty.subtitle"))
        self._create_btn.setText(tr("ui.empty.action_button"))
        self._hint_label.setText(tr("ui.empty.cli_hint"))
