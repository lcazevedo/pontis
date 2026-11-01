# SPDX-License-Identifier: GPL-3.0-or-later
"""Theme manager providing Light, Dark, and System stylesheets."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QWidget


class ThemeMode(StrEnum):
    """Supported visual theme modes."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


_LIGHT_QSS = """
QMainWindow {
    background-color: #f8fafc;
}

QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    padding: 4px 8px;
    spacing: 6px;
}

QToolButton {
    background-color: transparent;
    color: #1e293b;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: #f1f5f9;
    border: 1px solid #cbd5e1;
}

QToolButton:pressed {
    background-color: #e2e8f0;
}

QToolButton:disabled {
    color: #94a3b8;
}

QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    color: #0f172a;
    gridline-color: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    selection-background-color: #e0f2fe;
    selection-color: #0369a1;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #475569;
    font-weight: 600;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #cbd5e1;
}

QStatusBar {
    background-color: #f1f5f9;
    color: #475569;
    border-top: 1px solid #e2e8f0;
    padding: 2px 8px;
}

QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #1d4ed8;
}

QPushButton:pressed {
    background-color: #1e40af;
}

QLabel {
    color: #1e293b;
}
"""

_DARK_QSS = """
QMainWindow {
    background-color: #0f172a;
}

QToolBar {
    background-color: #1e293b;
    border-bottom: 1px solid #334155;
    padding: 4px 8px;
    spacing: 6px;
}

QToolButton {
    background-color: transparent;
    color: #f8fafc;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: #334155;
    border: 1px solid #475569;
}

QToolButton:pressed {
    background-color: #475569;
}

QToolButton:disabled {
    color: #64748b;
}

QTableWidget {
    background-color: #1e293b;
    alternate-background-color: #182234;
    color: #f8fafc;
    gridline-color: #334155;
    border: 1px solid #334155;
    border-radius: 6px;
    selection-background-color: #0369a1;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    font-weight: 600;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid #334155;
    border-bottom: 1px solid #334155;
}

QStatusBar {
    background-color: #1e293b;
    color: #94a3b8;
    border-top: 1px solid #334155;
    padding: 2px 8px;
}

QPushButton {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #2563eb;
}

QPushButton:pressed {
    background-color: #1d4ed8;
}

QLabel {
    color: #f8fafc;
}
"""


def apply_theme(target: QWidget | QApplication, mode: ThemeMode) -> None:
    """Apply the requested stylesheet to the target widget or application."""
    if mode == ThemeMode.LIGHT:
        target.setStyleSheet(_LIGHT_QSS)
    elif mode == ThemeMode.DARK:
        target.setStyleSheet(_DARK_QSS)
    else:
        target.setStyleSheet("")
