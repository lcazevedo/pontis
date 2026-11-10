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
    from pontis.infra.settings import load_settings
    from pontis.ui.main_window import MainWindow

    settings = load_settings()
    custom_rclone = settings.rclone_path if settings.rclone_path else None
    return MainWindow(
        db_path=db_path,
        rclone_binary=custom_rclone,
        check_updates_on_startup=settings.check_updates_on_startup,
    )


def main() -> int:
    """Dispatch to the CLI if arguments were given, else run the Qt application."""
    if len(sys.argv) > 1:
        # If the user passed CLI subcommands (e.g. profile, run, remote), run the CLI
        from pontis.cli import main as cli_main

        return cli_main(sys.argv[1:])

    from PySide6.QtWidgets import QApplication

    from pontis.i18n import set_language
    from pontis.infra.settings import load_settings
    from pontis.ui.theme import ThemeMode, apply_theme

    settings = load_settings()
    if settings.language:
        set_language(settings.language)

    app = QApplication(sys.argv)
    if settings.theme:
        try:
            apply_theme(app, ThemeMode(settings.theme))
        except ValueError:
            apply_theme(app, ThemeMode.SYSTEM)

    window = create_window()
    window.show()
    return app.exec()
