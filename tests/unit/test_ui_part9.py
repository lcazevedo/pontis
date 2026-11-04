# SPDX-License-Identifier: GPL-3.0-or-later
"""UI unit tests for Parte 9 (WatchDialog and MainWindow import/export actions)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from pontis.domain.models import Endpoint, SyncProfile
from pontis.services.profile_service import ProfileService
from pontis.services.remote_service import RemoteService
from pontis.services.run_service import RunService
from pontis.services.watch_service import WatchService
from pontis.ui.main_window import MainWindow
from pontis.ui.watch_dialog import WatchDialog

os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_watch_dialog_ui(qtbot: object, tmp_path: Path) -> None:
    """Test WatchDialog interaction, start/stop and logging."""
    local_dir = tmp_path / "watch_ui_folder"
    local_dir.mkdir()

    profile = SyncProfile(
        name="UIWatchProfile",
        side_a=Endpoint.local(str(local_dir)),
        side_b=Endpoint.cloud("remote", "folder"),
        id=12,
    )

    mock_run_service = MagicMock(spec=RunService)
    watch_service = WatchService()

    dialog = WatchDialog(
        profile=profile,
        run_service=mock_run_service,
        watch_service=watch_service,
    )
    dialog.show()

    assert dialog._btn_toggle.isEnabled()
    assert dialog._debounce_spin.value() == 5.0

    # Toggle to start watching
    dialog._btn_toggle.click()
    assert dialog._is_watching
    assert watch_service.is_watching(12)
    assert not dialog._debounce_spin.isEnabled()

    # Simulate a file change event
    dialog._bridge.file_changed.emit("modified", str(local_dir / "file.txt"))
    assert "file.txt" in dialog._log_text.toPlainText()

    # Toggle to stop watching
    dialog._btn_toggle.click()
    assert not dialog._is_watching
    assert not watch_service.is_watching(12)
    assert dialog._debounce_spin.isEnabled()

    # Clear log
    dialog._btn_clear_log.click()
    assert dialog._log_text.toPlainText() == ""

    dialog.close()


def test_main_window_part9_actions(qtbot: object, tmp_path: Path) -> None:
    """Test that MainWindow has the new actions and updates enabled state appropriately."""
    db_path = tmp_path / "mw_test.db"
    service = ProfileService(db_path=db_path)

    p = SyncProfile(
        name="TestPart9",
        side_a=Endpoint.local(str(tmp_path)),
        side_b=Endpoint.cloud("remote", "folder"),
    )
    service.add_profile(p)

    remote_service = MagicMock(spec=RemoteService)
    run_service = MagicMock(spec=RunService)

    win = MainWindow(
        service=service,
        remote_service=remote_service,
        run_service=run_service,
        db_path=db_path,
    )
    win.show()

    # Verify actions exist
    assert hasattr(win, "_action_watch")
    assert hasattr(win, "_action_import_profile")
    assert hasattr(win, "_action_export_profile")
    assert hasattr(win, "_action_import_script")

    # When no row is selected:
    win._table.clearSelection()
    win._on_selection_changed()
    assert not win._action_watch.isEnabled()
    assert not win._action_export_profile.isEnabled()
    assert win._action_import_profile.isEnabled()
    assert win._action_import_script.isEnabled()

    # When a row is selected:
    win._table.selectRow(0)
    win._on_selection_changed()
    assert win._action_watch.isEnabled()
    assert win._action_export_profile.isEnabled()

    win.close()
