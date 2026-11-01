# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit and UI tests for MainWindow."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from pontis.cli import main as cli_main
from pontis.domain.models import (
    Endpoint,
    RunResult,
    RunStatus,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.i18n import set_language, tr
from pontis.infra.database import connect
from pontis.services.profile_service import ProfileService
from pontis.ui.main_window import MainWindow
from pontis.ui.theme import ThemeMode


def _cell_text(window: MainWindow, row: int, col: int) -> str:
    item = window._table.item(row, col)
    assert item is not None
    return item.text()


@pytest.fixture
def service_with_profiles(tmp_path: Path) -> ProfileService:
    db_path = tmp_path / "gui_test.db"
    conn = connect(db_path)
    service = ProfileService(conn=conn)

    p1 = service.add_profile(
        SyncProfile(
            name="WorkDocs",
            side_a=Endpoint.local("/home/user/work"),
            side_b=Endpoint.cloud("gdrive", "work_backup"),
            options=SyncOptions(direction=SyncDirection.BIDIRECTIONAL),
        )
    )
    service.add_profile(
        SyncProfile(
            name="Photos",
            side_a=Endpoint.local("/home/user/photos"),
            side_b=Endpoint.cloud("onedrive", "photos"),
            options=SyncOptions(direction=SyncDirection.A_TO_B),
        )
    )

    # Add a run to p1
    assert p1.id is not None
    service._run_repo.add(
        RunResult(
            profile_id=p1.id,
            status=RunStatus.SUCCESS,
            files_transferred=10,
        )
    )

    return service


def test_main_window_empty_state(qtbot: QtBot, tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    conn = connect(db_path)
    service = ProfileService(conn=conn)

    window = MainWindow(service=service)
    qtbot.addWidget(window)
    window.show()

    # When no profiles exist, index 1 (EmptyStateWidget) is active
    assert window._stack.currentIndex() == 1
    assert not window._action_delete.isEnabled()
    assert window._table.rowCount() == 0


def test_main_window_shows_profiles(qtbot: QtBot, service_with_profiles: ProfileService) -> None:
    window = MainWindow(service=service_with_profiles)
    qtbot.addWidget(window)
    window.show()

    # Table view active
    assert window._stack.currentIndex() == 0
    assert window._table.rowCount() == 2

    # Verify rows (alphabetical order by name: Photos, WorkDocs)
    row0_name = _cell_text(window, 0, 0)
    row1_name = _cell_text(window, 1, 0)
    assert row0_name == "Photos"
    assert row1_name == "WorkDocs"

    # Verify Photos columns
    assert _cell_text(window, 0, 1) == "/home/user/photos"
    assert _cell_text(window, 0, 2) == "→"
    assert _cell_text(window, 0, 3) == "onedrive:photos"
    assert tr("ui.status.never_run") in _cell_text(window, 0, 5)

    # Verify WorkDocs columns
    assert _cell_text(window, 1, 1) == "/home/user/work"
    assert _cell_text(window, 1, 2) == "↔"
    assert _cell_text(window, 1, 3) == "gdrive:work_backup"
    assert tr("ui.status.success") in _cell_text(window, 1, 5)


def test_main_window_selection_enables_delete(
    qtbot: QtBot, service_with_profiles: ProfileService
) -> None:
    window = MainWindow(service=service_with_profiles)
    qtbot.addWidget(window)
    window.show()

    assert not window._action_delete.isEnabled()

    # Select the first row
    window._table.selectRow(0)
    assert window._action_delete.isEnabled()

    # Clear selection
    window._table.clearSelection()
    assert not window._action_delete.isEnabled()


def test_main_window_delete_profile_cancelled(
    qtbot: QtBot,
    service_with_profiles: ProfileService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow(service=service_with_profiles)
    qtbot.addWidget(window)
    window.show()

    window._table.selectRow(0)

    # Simulate user answering "No" to the confirmation dialog
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )

    window._action_delete.trigger()

    # Profile should still exist
    assert len(service_with_profiles.list_profiles()) == 2
    assert window._table.rowCount() == 2


def test_main_window_delete_profile_confirmed(
    qtbot: QtBot,
    service_with_profiles: ProfileService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow(service=service_with_profiles)
    qtbot.addWidget(window)
    window.show()

    # Select "Photos" row
    window._table.selectRow(0)
    deleted_name = _cell_text(window, 0, 0)

    # Simulate user answering "Yes" to the confirmation dialog
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    window._action_delete.trigger()

    # "Photos" should be removed from database and table
    remaining = service_with_profiles.list_profiles()
    assert len(remaining) == 1
    assert remaining[0].name != deleted_name
    assert window._table.rowCount() == 1

    # Delete the second profile too
    window._table.selectRow(0)
    window._action_delete.trigger()

    # Now empty state should appear
    assert len(service_with_profiles.list_profiles()) == 0
    assert window._table.rowCount() == 0
    assert window._stack.currentIndex() == 1


def test_main_window_theme_switching(qtbot: QtBot, service_with_profiles: ProfileService) -> None:
    window = MainWindow(service=service_with_profiles)
    qtbot.addWidget(window)
    window.show()

    for mode in (ThemeMode.DARK, ThemeMode.LIGHT, ThemeMode.SYSTEM):
        window.set_theme(mode)
        assert window._current_theme == mode
        if mode == ThemeMode.DARK:
            assert "background-color: #0f172a;" in window.styleSheet()
        elif mode == ThemeMode.LIGHT:
            assert "background-color: #f8fafc;" in window.styleSheet()
        else:
            assert window.styleSheet() == ""
    assert window._current_theme == ThemeMode.SYSTEM
    assert window.styleSheet() == ""


def test_main_window_translations(qtbot: QtBot, tmp_path: Path) -> None:
    try:
        set_language("pt_BR")
        assert tr("ui.table.header.name") == "Nome"
        assert tr("ui.actions.new") == "Novo Perfil"

        db_path = tmp_path / "i18n.db"
        conn = connect(db_path)
        service = ProfileService(conn=conn)
        window = MainWindow(service=service)
        qtbot.addWidget(window)

        assert "Perfis" in window.windowTitle() or "Pontis" in window.windowTitle()

        set_language("en")
        assert tr("ui.table.header.name") == "Name"
        assert tr("ui.actions.new") == "New Profile"
    finally:
        set_language(None)


def test_cli_created_profiles_appear_in_window_and_can_be_deleted(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End-to-end verification of Part 4 test criterion.

    Profiles created via CLI appear in the GUI window and can be deleted from it.
    """
    db_path = tmp_path / "integration_p4.db"
    dir_a = tmp_path / "folder_a"
    dir_b = tmp_path / "folder_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # 1. Create a profile via the CLI
    code = cli_main(
        [
            "--db",
            str(db_path),
            "profile",
            "add",
            "TestSyncCLI",
            "--a",
            str(dir_a),
            "--b",
            str(dir_b),
        ]
    )
    assert code == 0

    # 2. Open the GUI window pointing to the same database
    window = MainWindow(db_path=db_path)
    qtbot.addWidget(window)
    window.show()

    # Profile appears in the GUI
    assert window._stack.currentIndex() == 0
    assert window._table.rowCount() == 1
    assert _cell_text(window, 0, 0) == "TestSyncCLI"
    assert _cell_text(window, 0, 1) == str(dir_a.resolve())
    assert _cell_text(window, 0, 3) == str(dir_b.resolve())

    # 3. Delete the profile through the GUI
    window._table.selectRow(0)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window._action_delete.trigger()

    # GUI shows empty state
    assert window._table.rowCount() == 0
    assert window._stack.currentIndex() == 1

    # 4. Verify via CLI that the profile is truly gone from SQLite
    capsys.readouterr()  # clear buffer
    code_list = cli_main(["--db", str(db_path), "profile", "list"])
    assert code_list == 0
    out = capsys.readouterr().out
    assert "TestSyncCLI" not in out
