# SPDX-License-Identifier: GPL-3.0-or-later
"""Application bootstrap: CLI when arguments are given, otherwise the (still empty) window."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow


def create_window() -> QMainWindow:
    """Create the empty main window."""
    from PySide6.QtWidgets import QMainWindow

    window = QMainWindow()
    window.setWindowTitle("Pontis")
    window.resize(800, 500)
    return window


def main() -> int:
    """Dispatch to the CLI if arguments were given, else run the Qt application."""
    if len(sys.argv) > 1:
        from pontis.cli import main as cli_main

        return cli_main(sys.argv[1:])

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = create_window()
    window.show()
    return app.exec()
