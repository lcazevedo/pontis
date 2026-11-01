# SPDX-License-Identifier: GPL-3.0-or-later
"""Application bootstrap: CLI when subcommands are given, otherwise the main window."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pontis.ui.main_window import MainWindow


def create_window(db_path: Path | None = None) -> MainWindow:
    """Create and configure the Pontis main window."""
    from pontis.ui.main_window import MainWindow

    return MainWindow(db_path=db_path)


def main() -> int:
    """Dispatch to the CLI if arguments were given, else run the Qt application."""
    if len(sys.argv) > 1:
        # If the user passed CLI subcommands (e.g. profile, run, remote), run the CLI
        from pontis.cli import main as cli_main

        return cli_main(sys.argv[1:])

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = create_window()
    window.show()
    return app.exec()
