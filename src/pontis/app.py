# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal application bootstrap: opens an empty window (environment proof only)."""

import sys

from PySide6.QtWidgets import QApplication, QMainWindow


def create_window() -> QMainWindow:
    """Create the empty main window."""
    window = QMainWindow()
    window.setWindowTitle("Pontis")
    window.resize(800, 500)
    return window


def main() -> int:
    """Run the Qt application and return its exit code."""
    app = QApplication(sys.argv)
    window = create_window()
    window.show()
    return app.exec()
