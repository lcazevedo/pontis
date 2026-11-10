# SPDX-License-Identifier: GPL-3.0-or-later
"""UI tests for Part 10: Preferences, runtime language switching, and update dialogs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pontis.i18n import (
    _CATALOG,
    current_language,
    register_language_listener,
    set_language,
    tr,
    unregister_language_listener,
)
from pontis.infra.settings import AppSettings, SettingsManager
from pontis.services.update_service import UpdateInfo
from pontis.ui.about_dialog import AboutDialog
from pontis.ui.main_window import MainWindow
from pontis.ui.preferences_dialog import PreferencesDialog
from pontis.ui.theme import _DARK_QSS, _LIGHT_QSS, ThemeMode, apply_theme
from pontis.ui.update_dialog import UpdateDialog

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot


def test_i18n_catalog_exact_parity() -> None:
    """Every string key in 'en' must exist in 'pt_BR' and vice-versa."""
    en_keys = set(_CATALOG["en"].keys())
    pt_keys = set(_CATALOG["pt_BR"].keys())

    missing_in_pt = en_keys - pt_keys
    missing_in_en = pt_keys - en_keys

    assert not missing_in_pt, f"Keys present in EN but missing in PT-BR: {missing_in_pt}"
    assert not missing_in_en, f"Keys present in PT-BR but missing in EN: {missing_in_en}"


def test_i18n_runtime_listeners() -> None:
    """register_language_listener invokes callbacks when set_language changes the language."""
    invocations: list[str] = []

    def on_change() -> None:
        invocations.append(current_language())

    register_language_listener(on_change)
    try:
        set_language("en")
        assert tr("ui.actions.new") == "New Profile"

        set_language("pt_BR")
        assert tr("ui.actions.new") == "Novo Perfil"

        assert len(invocations) >= 1
    finally:
        unregister_language_listener(on_change)


def test_main_window_live_language_switching(qtbot: QtBot, tmp_path: Path) -> None:
    """MainWindow retranslates its window title, table headers, actions, and menus live."""
    db_file = tmp_path / "test.db"
    settings_file = tmp_path / "settings.json"
    manager = SettingsManager(settings_file)

    set_language("pt_BR")
    win = MainWindow(db_path=db_file, settings_manager=manager, check_updates_on_startup=False)
    qtbot.addWidget(win)

    # Initially in PT-BR
    assert "Sincronização" in win.windowTitle()
    assert win._action_new.text() == "Novo Perfil"
    col0_pt = win._table.horizontalHeaderItem(0)
    assert col0_pt is not None and col0_pt.text() == "Nome"

    # Switch live to EN
    set_language("en")
    assert "Two-Way File Sync" in win.windowTitle()
    assert win._action_new.text() == "New Profile"
    col0_en = win._table.horizontalHeaderItem(0)
    assert col0_en is not None and col0_en.text() == "Name"
    assert win._action_preferences.text() == "Preferences..."

    # Switch live back to PT-BR
    set_language("pt_BR")
    assert "Sincronização" in win.windowTitle()
    assert win._action_new.text() == "Novo Perfil"
    col0_pt_again = win._table.horizontalHeaderItem(0)
    assert col0_pt_again is not None and col0_pt_again.text() == "Nome"
    assert win._action_preferences.text() == "Preferências..."


def test_preferences_dialog_save_and_apply(qtbot: QtBot, tmp_path: Path) -> None:
    """PreferencesDialog modifies AppSettings and applies runtime changes."""
    settings_file = tmp_path / "settings.json"
    manager = SettingsManager(settings_file)
    manager.save(AppSettings(language="pt_BR", theme="system"))

    dialog = PreferencesDialog(settings_manager=manager)
    qtbot.addWidget(dialog)

    # Change language to EN and theme to dark
    en_idx = dialog._combo_language.findData("en")
    dialog._combo_language.setCurrentIndex(en_idx)

    dark_idx = dialog._combo_theme.findData("dark")
    dialog._combo_theme.setCurrentIndex(dark_idx)

    dialog.apply_settings()

    # Verify settings persisted to disk
    reloaded = manager.load()
    assert reloaded.language == "en"
    assert reloaded.theme == "dark"
    assert current_language() == "en"

    # Reset language for clean state
    set_language("pt_BR")


def test_about_dialog(qtbot: QtBot) -> None:
    """AboutDialog renders project description, license, and action buttons."""
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert "Pontis" in dialog.windowTitle()
    assert dialog.isModal() is False


def test_update_dialog_update_available(qtbot: QtBot) -> None:
    """UpdateDialog displays release notes and ignore version option when update is available."""
    info = UpdateInfo(
        has_update=True,
        current_version="0.1.0",
        latest_version="1.2.0",
        release_name="v1.2.0 Release",
        release_notes="* Added polished dark mode",
        release_url="https://github.com/lcazevedo/pontis/releases/tag/v1.2.0",
        published_at="2026-11-10T10:00:00Z",
        html_url="https://github.com/lcazevedo/pontis/releases/tag/v1.2.0",
        tag_name="v1.2.0",
    )

    dialog = UpdateDialog(info)
    qtbot.addWidget(dialog)

    assert dialog._info.has_update is True
    assert hasattr(dialog, "_ignore_checkbox")
    assert dialog._notes_browser.toPlainText() == "* Added polished dark mode"

    # Check ignore version checkbox
    dialog._ignore_checkbox.setChecked(True)
    dialog._on_close()
    assert dialog.ignore_requested is True


def test_update_dialog_already_latest(qtbot: QtBot) -> None:
    """UpdateDialog confirms that the app is on the newest version."""
    info = UpdateInfo(
        has_update=False,
        current_version="1.0.0",
        latest_version="1.0.0",
        release_name="v1.0.0",
        release_notes="",
        release_url="",
        published_at="",
        html_url="",
        tag_name="v1.0.0",
    )

    dialog = UpdateDialog(info)
    qtbot.addWidget(dialog)

    assert dialog._info.has_update is False
    assert not hasattr(dialog, "_notes_browser")


def test_accessibility_keyboard_and_contrast(qtbot: QtBot, tmp_path: Path) -> None:
    """Verify keyboard shortcuts, accessible names, and high contrast focus styles."""
    db_file = tmp_path / "test.db"
    settings_file = tmp_path / "settings.json"
    manager = SettingsManager(settings_file)

    win = MainWindow(db_path=db_file, settings_manager=manager, check_updates_on_startup=False)
    qtbot.addWidget(win)

    # Keyboard shortcuts
    assert win._action_preferences.shortcut().toString() == "Ctrl+,"
    assert win._action_about.shortcut().toString() == "F1"
    assert win._action_sync.shortcut().toString() == "Ctrl+R"
    assert win._action_history.shortcut().toString() == "Ctrl+H"
    assert win._action_watch.shortcut().toString() == "Ctrl+W"

    # Accessibility attributes for screen readers
    assert win._table.accessibleName() != ""
    assert win._table.accessibleDescription() != ""

    # Theme contrast & focus indicators in QSS
    assert ":focus" in _LIGHT_QSS
    assert ":focus" in _DARK_QSS
    assert "border: 2px solid" in _LIGHT_QSS
    assert "border: 2px solid" in _DARK_QSS

    # Switching themes applies valid stylesheets
    apply_theme(win, ThemeMode.DARK)
    assert win.styleSheet() == _DARK_QSS

    apply_theme(win, ThemeMode.LIGHT)
    assert win.styleSheet() == _LIGHT_QSS
