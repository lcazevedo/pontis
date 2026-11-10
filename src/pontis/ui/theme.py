# SPDX-License-Identifier: GPL-3.0-or-later
"""Theme manager providing Light, Dark, and System stylesheets.

Includes high contrast colors and keyboard focus indicators.
"""

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
QMainWindow, QDialog {
    background-color: #f8fafc;
    color: #0f172a;
}

QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #cbd5e1;
    padding: 4px 8px;
    spacing: 6px;
}

QToolButton {
    background-color: transparent;
    color: #0f172a;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: #f1f5f9;
    border: 1px solid #94a3b8;
}

QToolButton:pressed {
    background-color: #e2e8f0;
}

QToolButton:focus {
    border: 2px solid #2563eb;
}

QToolButton:disabled {
    color: #94a3b8;
}

QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    color: #0f172a;
    gridline-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    selection-background-color: #e0f2fe;
    selection-color: #0369a1;
}

QTableWidget:focus {
    border: 2px solid #2563eb;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #1e293b;
    font-weight: 600;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid #cbd5e1;
    border-bottom: 1px solid #94a3b8;
}

QStatusBar {
    background-color: #f1f5f9;
    color: #334155;
    border-top: 1px solid #cbd5e1;
    padding: 2px 8px;
}

QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid transparent;
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

QPushButton:focus {
    border: 2px solid #0f172a;
    outline: none;
}

QPushButton:disabled {
    background-color: #e2e8f0;
    color: #94a3b8;
    border: 1px solid #cbd5e1;
}

QLabel {
    color: #0f172a;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #94a3b8;
    border-radius: 4px;
    padding: 6px 10px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 2px solid #2563eb;
}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QComboBox:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
}

QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background-color: #ffffff;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #f1f5f9;
    color: #334155;
    padding: 8px 16px;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #2563eb;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #e2e8f0;
}

QTabBar::tab:focus {
    border: 2px solid #2563eb;
}

QGroupBox {
    font-weight: 600;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 14px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #1e293b;
}

QCheckBox, QRadioButton {
    color: #0f172a;
    spacing: 8px;
}

QCheckBox:focus, QRadioButton:focus {
    border: 1px dotted #2563eb;
}

QScrollBar:vertical {
    background: #f1f5f9;
    width: 12px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 20px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
"""

_DARK_QSS = """
QMainWindow, QDialog {
    background-color: #0f172a;
    color: #f8fafc;
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

QToolButton:focus {
    border: 2px solid #60a5fa;
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

QTableWidget:focus {
    border: 2px solid #60a5fa;
}

QHeaderView::section {
    background-color: #0f172a;
    color: #e2e8f0;
    font-weight: 600;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid #334155;
    border-bottom: 1px solid #475569;
}

QStatusBar {
    background-color: #1e293b;
    color: #cbd5e1;
    border-top: 1px solid #334155;
    padding: 2px 8px;
}

QPushButton {
    background-color: #3b82f6;
    color: #ffffff;
    border: 1px solid transparent;
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

QPushButton:focus {
    border: 2px solid #ffffff;
    outline: none;
}

QPushButton:disabled {
    background-color: #334155;
    color: #64748b;
    border: 1px solid #1e293b;
}

QLabel {
    color: #f8fafc;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 6px 10px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 2px solid #60a5fa;
}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QComboBox:disabled {
    background-color: #0f172a;
    color: #64748b;
}

QTabWidget::pane {
    border: 1px solid #334155;
    background-color: #1e293b;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 8px 16px;
    border: 1px solid #334155;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #1e293b;
    color: #60a5fa;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #182234;
}

QTabBar::tab:focus {
    border: 2px solid #60a5fa;
}

QGroupBox {
    font-weight: 600;
    border: 1px solid #334155;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 14px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #e2e8f0;
}

QCheckBox, QRadioButton {
    color: #f8fafc;
    spacing: 8px;
}

QCheckBox:focus, QRadioButton:focus {
    border: 1px dotted #60a5fa;
}

QScrollBar:vertical {
    background: #0f172a;
    width: 12px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
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
