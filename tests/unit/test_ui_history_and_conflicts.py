# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI tests for HistoryDialog, ConflictResolutionDialog, and bisync error handling."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMessageBox

from pontis.domain.models import (
    Endpoint,
    RunResult,
    RunStatus,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.infra.database import connect
from pontis.infra.rclone_adapter import AdapterOutcome
from pontis.infra.repositories import ProfileRepository, RunRepository
from pontis.infra.run_logger import RunLogManager
from pontis.services.conflict_service import ConflictResolution, ConflictService
from pontis.services.profile_service import ProfileService
from pontis.ui.conflict_resolution_dialog import ConflictResolutionDialog
from pontis.ui.history_dialog import HistoryDialog
from pontis.ui.main_window import MainWindow
from pontis.ui.sync_progress_dialog import SyncProgressDialog

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot


def _create_test_profile(tmp_path: Path, name: str = "TestProfile", pid: int = 1) -> SyncProfile:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(exist_ok=True)
    b.mkdir(exist_ok=True)
    return SyncProfile(
        id=pid,
        name=name,
        side_a=Endpoint.local(str(a)),
        side_b=Endpoint.local(str(b)),
        options=SyncOptions(direction=SyncDirection.BIDIRECTIONAL),
    )


def test_history_dialog_view_and_filters(qtbot: QtBot, tmp_path: Path) -> None:
    db_path = tmp_path / "history_test.db"
    conn = connect(db_path)
    p_repo = ProfileRepository(conn)
    r_repo = RunRepository(conn)

    p1 = p_repo.add(
        SyncProfile(name="ProfileAlpha", side_a=Endpoint.local("/a"), side_b=Endpoint.local("/b"))
    )
    p2 = p_repo.add(
        SyncProfile(name="ProfileBeta", side_a=Endpoint.local("/c"), side_b=Endpoint.local("/d"))
    )
    assert p1.id is not None and p2.id is not None

    r1 = r_repo.add(RunResult(profile_id=p1.id, status=RunStatus.SUCCESS, files_transferred=5))
    r2 = r_repo.add(
        RunResult(profile_id=p1.id, status=RunStatus.ERROR, errors=1, message="Disk full")
    )
    r_repo.add(
        RunResult(profile_id=p2.id, status=RunStatus.SUCCESS, files_transferred=2, dry_run=True)
    )
    assert r1.id is not None and r2.id is not None

    log_mgr = RunLogManager(log_dir=tmp_path / "logs")
    w1 = log_mgr.create_writer(r1.id, p1.name, dry_run=False, command=["rclone"])
    w1.write_raw_line("Transferred 5 files successfully")
    w1.finish(RunStatus.SUCCESS, 5, 0, 0)

    service = ProfileService(conn=conn)
    dialog = HistoryDialog(service, log_dir=tmp_path / "logs")
    qtbot.addWidget(dialog)
    dialog.show()

    # Initial view: All profiles -> 3 rows
    assert dialog._table.rowCount() == 3

    # Filter to ProfileAlpha only
    idx = dialog._combo_profile.findData(p1.id)
    dialog._combo_profile.setCurrentIndex(idx)
    assert dialog._table.rowCount() == 2

    # Filter to Status: Errors only
    status_idx = dialog._combo_status.findData("error")
    dialog._combo_status.setCurrentIndex(status_idx)
    assert dialog._table.rowCount() == 1
    item = dialog._table.item(0, 0)
    assert item is not None and item.text() == str(r2.id)
    assert "Disk full" in dialog._lbl_details_meta.text()

    # Reset status filter and select run 1 to check log
    dialog._combo_status.setCurrentIndex(dialog._combo_status.findData("all"))
    assert dialog._table.rowCount() == 2
    # Select row with r1
    for row in range(dialog._table.rowCount()):
        item_id = dialog._table.item(row, 0)
        if item_id and item_id.text() == str(r1.id):
            dialog._table.selectRow(row)
            break

    assert "Transferred 5 files successfully" in dialog._log_edit.toPlainText()

    # Test copy log
    dialog._on_copy_log()
    assert "Transferred 5 files successfully" in QGuiApplication.clipboard().text()

    # Test export log
    export_file = tmp_path / "saved_run.log"
    with (
        patch(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            return_value=(str(export_file), "Log Files"),
        ),
        patch.object(QMessageBox, "information") as mock_info,
    ):
        dialog._on_export_log()
        assert export_file.is_file()
        assert "Transferred 5 files successfully" in export_file.read_text(encoding="utf-8")
        assert mock_info.called

    # Test clear history
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog._on_clear_history()
        assert dialog._table.rowCount() == 0


def test_conflict_resolution_dialog_interaction(qtbot: QtBot, tmp_path: Path) -> None:
    side_a = tmp_path / "side_a"
    side_b = tmp_path / "side_b"
    side_a.mkdir()
    side_b.mkdir()

    (side_a / "document.txt.conflict1").write_text("Side A text", encoding="utf-8")
    (side_a / "document.txt.conflict2").write_text("Side B text", encoding="utf-8")
    (side_a / "image.png.conflict1").write_text("img A", encoding="utf-8")
    (side_a / "image.png.conflict2").write_text("img B", encoding="utf-8")

    profile = _create_test_profile(tmp_path, name="ConfProfile")
    profile.side_a = Endpoint.local(str(side_a))
    profile.side_b = Endpoint.local(str(side_b))

    conflict_svc = ConflictService()
    dialog = ConflictResolutionDialog(profile, conflict_service=conflict_svc)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog._table.rowCount() == 2

    # Check preview on selection
    dialog._table.selectRow(0)
    assert "Side A text" in dialog._preview_a.toPlainText()
    assert "Side B text" in dialog._preview_b.toPlainText()

    # Test batch button: Manter Lado A
    dialog._set_all_resolutions(ConflictResolution.KEEP_SIDE_A)
    for combo in dialog._combos.values():
        assert combo.currentData() == ConflictResolution.KEEP_SIDE_A

    # Test apply
    with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Yes):
        dialog._on_apply()

    assert (side_a / "document.txt").is_file()
    assert (side_a / "document.txt").read_text(encoding="utf-8") == "Side A text"
    assert dialog.should_sync_after is True


def test_sync_progress_resync_handling(qtbot: QtBot, tmp_path: Path) -> None:
    profile = _create_test_profile(tmp_path)
    res_error = RunResult(
        profile_id=1,
        status=RunStatus.ERROR,
        message="Bisync critical error: Must run --resync to recover.",
    )
    outcome_error = AdapterOutcome(
        returncode=1,
        command=["rclone"],
        needs_resync=True,
    )
    run_service = MagicMock()
    run_service.run.return_value = res_error
    run_service.last_outcome = outcome_error

    dialog = SyncProgressDialog(profile, run_service, dry_run=False)
    qtbot.addWidget(dialog)
    dialog.show()

    # Trigger worker finished with resync error
    dialog._on_finished(res_error, outcome_error)

    # Verify resync button is visible
    assert not dialog._btn_resync.isHidden()

    # Clicking resync triggers prompt; if confirmed, emits resync_requested
    resync_emitted = False

    def _on_resync() -> None:
        nonlocal resync_emitted
        resync_emitted = True

    dialog.resync_requested.connect(_on_resync)

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog._on_resync_clicked()
        assert resync_emitted is True


def test_sync_progress_conflict_handling(qtbot: QtBot, tmp_path: Path) -> None:
    profile = _create_test_profile(tmp_path)
    res_ok = RunResult(profile_id=1, status=RunStatus.SUCCESS)
    outcome_conflicts = AdapterOutcome(
        returncode=0,
        command=["rclone"],
        conflicts_detected=["file1.txt", "file2.txt"],
    )
    run_service = MagicMock()
    run_service.run.return_value = res_ok
    run_service.last_outcome = outcome_conflicts

    dialog = SyncProgressDialog(profile, run_service, dry_run=False)
    qtbot.addWidget(dialog)
    dialog.show()

    dialog._on_finished(res_ok, outcome_conflicts)
    assert not dialog._btn_conflicts.isHidden()
    assert "2" in dialog._btn_conflicts.text()


def test_main_window_history_and_conflicts_actions(qtbot: QtBot, tmp_path: Path) -> None:
    db_path = tmp_path / "mw_test.db"
    profile_service = ProfileService(db_path=db_path)
    side_a = tmp_path / "a"
    side_b = tmp_path / "b"
    side_a.mkdir()
    side_b.mkdir()
    profile_service.add_profile(
        SyncProfile(
            name="Alpha",
            side_a=Endpoint.local(str(side_a)),
            side_b=Endpoint.local(str(side_b)),
        )
    )

    window = MainWindow(service=profile_service, db_path=db_path)
    qtbot.addWidget(window)
    window.show()

    # Select profile row
    window._table.selectRow(0)
    assert window._action_history.isEnabled()
    assert window._action_conflicts.isEnabled()

    # Test opening history dialog
    with patch.object(HistoryDialog, "exec") as mock_exec:
        window._on_history()
        assert mock_exec.called

    # Test opening conflict resolution dialog
    with patch.object(ConflictResolutionDialog, "exec", return_value=0) as mock_conf:
        window._on_conflicts()
        assert mock_conf.called

    window.close()
