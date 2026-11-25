# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for Part 11: central links, discreet support UI, and About dialog support links."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from pontis.i18n import set_language
from pontis.infra.settings import SettingsManager
from pontis.links import (
    BUYMEACOFFEE_URL,
    GITHUB_ISSUES_URL,
    GITHUB_SECURITY_URL,
    GITHUB_SPONSORS_URL,
    GITHUB_URL,
    KOFI_URL,
    SUPPORT_LINKS,
)
from pontis.ui.about_dialog import AboutDialog
from pontis.ui.main_window import MainWindow

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot


def test_support_links_constants() -> None:
    """Repository and voluntary support links are valid HTTPS URLs without Pix."""
    urls = [
        GITHUB_URL,
        GITHUB_ISSUES_URL,
        GITHUB_SECURITY_URL,
        GITHUB_SPONSORS_URL,
        KOFI_URL,
        BUYMEACOFFEE_URL,
    ]
    for url in urls:
        assert url.startswith("https://")

    assert SUPPORT_LINKS == (
        ("ui.support.github_sponsors", GITHUB_SPONSORS_URL),
        ("ui.support.kofi", KOFI_URL),
        ("ui.support.buymeacoffee", BUYMEACOFFEE_URL),
    )


def test_main_window_discrete_support_widget(
    qtbot: QtBot, tmp_path: Path, monkeypatch: object
) -> None:
    """MainWindow exposes a discreet support menu button in the status bar with live i18n."""
    opened_urls: list[str] = []

    def _fake_open(url: QUrl) -> bool:
        opened_urls.append(url.toString())
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", _fake_open)  # type: ignore[attr-defined]

    db_file = tmp_path / "test.db"
    settings_file = tmp_path / "settings.json"
    manager = SettingsManager(settings_file)

    set_language("pt_BR")
    win = MainWindow(db_path=db_file, settings_manager=manager, check_updates_on_startup=False)
    qtbot.addWidget(win)

    assert win._support_button.objectName() == "supportStatusButton"
    assert win._support_button.accessibleName() != ""
    assert win._support_button.text() == "Apoiar"
    assert win._support_menu.title() == "Apoiar o Pontis"
    assert len(win._support_menu.actions()) == 3

    # Live language switch updates support button and Help submenu
    set_language("en")
    assert win._support_button.text() == "Support"
    assert win._support_menu.title() == "Support Pontis"

    # Trigger each support action and verify opened URL
    win._action_support_sponsors.trigger()
    win._action_support_kofi.trigger()
    win._action_support_bmc.trigger()

    assert opened_urls == [GITHUB_SPONSORS_URL, KOFI_URL, BUYMEACOFFEE_URL]

    set_language(None)


def test_about_dialog_support_buttons(qtbot: QtBot, monkeypatch: object) -> None:
    """AboutDialog renders voluntary support buttons that open the expected URLs."""
    opened_urls: list[str] = []

    def _fake_open(url: QUrl) -> bool:
        opened_urls.append(url.toString())
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", _fake_open)  # type: ignore[attr-defined]

    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    dialog._support_sponsors_btn.click()
    dialog._support_kofi_btn.click()
    dialog._support_bmc_btn.click()
    dialog._repo_button.click()

    assert opened_urls == [
        GITHUB_SPONSORS_URL,
        KOFI_URL,
        BUYMEACOFFEE_URL,
        GITHUB_URL,
    ]
