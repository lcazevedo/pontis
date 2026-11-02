# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for GUI sync execution: progress dialog, worker, dry-run summary, notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
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
from pontis.infra.locking import ProfileLockedError
from pontis.infra.rclone_adapter import AdapterOutcome, LogEvent, RcloneAdapter
from pontis.infra.repositories import ProfileRepository, RunRepository
from pontis.services.profile_service import ProfileService
from pontis.services.remote_service import RemoteService
from pontis.services.run_service import EndpointMissingError, RunService
from pontis.ui.dry_run_summary_dialog import DryRunSummaryDialog
from pontis.ui.main_window import MainWindow
from pontis.ui.notifications import send_notification
from pontis.ui.sync_progress_dialog import SyncProgressDialog
from pontis.ui.sync_worker import SyncWorker
from pontis.ui.widgets.cloud_browser_dialog import CloudFolderBrowserDialog

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot


def _make_profile(tmp_path: Path, name: str = "TestProfile", pid: int = 1) -> SyncProfile:
    a = tmp_path / "side_a"
    b = tmp_path / "side_b"
    a.mkdir(exist_ok=True)
    b.mkdir(exist_ok=True)
    return SyncProfile(
        name=name,
        side_a=Endpoint.local(str(a)),
        side_b=Endpoint.local(str(b)),
        options=SyncOptions(direction=SyncDirection.BIDIRECTIONAL),
        id=pid,
    )


def test_dry_run_summary_no_deletes(qtbot: QtBot, tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    outcome = AdapterOutcome(
        returncode=0,
        command=["rclone"],
        planned_copies=2,
        planned_copy_files=["file1.txt", "sub/file2.txt"],
        planned_deletes=0,
        planned_delete_files=[],
    )
    dialog = DryRunSummaryDialog(profile, outcome)
    qtbot.addWidget(dialog)

    assert dialog._copies_list.count() == 2
    assert dialog._deletes_list.count() == 1  # Empty state label
    assert dialog._btn_apply.isEnabled()
    assert not dialog.should_apply_sync

    dialog._on_apply()
    assert dialog.should_apply_sync


def test_dry_run_summary_with_mass_delete_confirmation(qtbot: QtBot, tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    outcome = AdapterOutcome(
        returncode=0,
        command=["rclone"],
        planned_copies=1,
        planned_copy_files=["keep.txt"],
        planned_deletes=3,
        planned_delete_files=["del1.txt", "del2.txt", "del3.txt"],
    )
    dialog = DryRunSummaryDialog(profile, outcome)
    qtbot.addWidget(dialog)

    assert dialog._copies_list.count() == 1
    assert dialog._deletes_list.count() == 3
    # With deletes, apply button must be disabled until user confirms
    assert not dialog._btn_apply.isEnabled()
    assert dialog._confirm_check is not None
    assert not dialog._confirm_check.isChecked()

    # User checks confirmation checkbox
    dialog._confirm_check.setChecked(True)
    assert dialog._btn_apply.isEnabled()

    dialog._on_apply()
    assert dialog.should_apply_sync


def test_sync_worker_success(qtbot: QtBot, tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    mock_run_service = MagicMock(spec=RunService)
    expected_result = RunResult(profile_id=1, status=RunStatus.SUCCESS, files_transferred=2)
    mock_run_service.run.return_value = expected_result
    mock_run_service.last_outcome = AdapterOutcome(returncode=0, command=[], transfers=2)

    worker = SyncWorker(profile, mock_run_service, dry_run=False)

    finished_events: list[tuple[object, object]] = []
    worker.finished_signal.connect(lambda res, out: finished_events.append((res, out)))

    with qtbot.waitSignal(worker.finished):
        worker.start()

    assert len(finished_events) == 1
    assert finished_events[0][0] == expected_result
    mock_run_service.run.assert_called_once()


def test_sync_worker_handles_locked_error(qtbot: QtBot, tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    mock_run_service = MagicMock(spec=RunService)
    mock_run_service.run.side_effect = ProfileLockedError("Already locked")

    worker = SyncWorker(profile, mock_run_service)
    errors: list[str] = []
    worker.error_signal.connect(errors.append)

    with qtbot.waitSignal(worker.finished):
        worker.start()

    assert len(errors) == 1
    assert "já está em execução" in errors[0] or "already" in errors[0].lower()


def test_sync_worker_handles_missing_endpoint(qtbot: QtBot, tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    mock_run_service = MagicMock(spec=RunService)
    mock_run_service.run.side_effect = EndpointMissingError("/nonexistent/disk")

    worker = SyncWorker(profile, mock_run_service)
    errors: list[str] = []
    worker.error_signal.connect(errors.append)

    with qtbot.waitSignal(worker.finished):
        worker.start()

    assert len(errors) == 1
    assert "/nonexistent/disk" in errors[0]


def test_sync_progress_dialog_ui_updates(qtbot: QtBot, tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    mock_run_service = MagicMock(spec=RunService)
    mock_run_service.run.return_value = RunResult(profile_id=1, status=RunStatus.SUCCESS)
    mock_run_service.last_outcome = AdapterOutcome(returncode=0, command=[])

    dialog = SyncProgressDialog(profile, mock_run_service, dry_run=True)
    qtbot.addWidget(dialog)

    # Simulate progress event
    dialog._on_progress(
        {
            "message": "Copying files",
            "transfers": 3,
            "deletes": 1,
            "errors": 0,
            "bytes": 2048,
            "totalBytes": 4096,
            "speed": 1024,
        }
    )

    assert dialog._lbl_transfers.text() == "3"
    assert dialog._lbl_deletes.text() == "1"
    assert dialog._lbl_errors.text() == "0"
    assert "KB" in dialog._lbl_bytes.text()
    assert dialog._progress_bar.value() == 50

    # Simulate log event
    dialog._on_log("info", "Starting comparison")
    assert "Starting comparison" in dialog._log_edit.toPlainText()


def test_main_window_sync_actions_enabled_on_selection(qtbot: QtBot, tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    profiles = ProfileRepository(conn)
    service = ProfileService(conn=conn)
    profiles.add(_make_profile(tmp_path, "DemoProfile"))

    mock_run_service = MagicMock(spec=RunService)
    mock_run_service.needs_first_run_dry_run.return_value = False

    window = MainWindow(service=service, run_service=mock_run_service)
    qtbot.addWidget(window)
    window.load_profiles()

    assert not window._action_sync.isEnabled()
    assert not window._action_dry_run.isEnabled()

    # Select profile row
    window._table.selectRow(0)
    assert window._action_sync.isEnabled()
    assert window._action_dry_run.isEnabled()

    # Deselect row
    window._table.clearSelection()
    assert not window._action_sync.isEnabled()
    assert not window._action_dry_run.isEnabled()


def test_main_window_first_run_dry_run_prompt(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "test.db")
    profiles = ProfileRepository(conn)
    service = ProfileService(conn=conn)
    profiles.add(_make_profile(tmp_path, "FirstTimeProfile"))

    mock_run_service = MagicMock(spec=RunService)
    mock_run_service.needs_first_run_dry_run.return_value = True

    window = MainWindow(service=service, run_service=mock_run_service)
    qtbot.addWidget(window)
    window.load_profiles()
    window._table.selectRow(0)

    executed_calls: list[tuple[bool, bool]] = []

    def mock_execute(prof: SyncProfile, *, dry_run: bool, is_first_run: bool = False) -> None:
        executed_calls.append((dry_run, is_first_run))

    monkeypatch.setattr(window, "_execute_profile", mock_execute)

    # User clicks Cancel on the first run prompt
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    window._on_sync_now()
    assert len(executed_calls) == 0

    # User clicks OK on the first run prompt
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window._on_sync_now()
    assert len(executed_calls) == 1
    assert executed_calls[0] == (True, True)  # (dry_run=True, is_first_run=True)


def test_main_window_prevents_duplicate_execution(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "test.db")
    profiles = ProfileRepository(conn)
    service = ProfileService(conn=conn)
    prof = profiles.add(_make_profile(tmp_path, "ActiveProfile"))

    mock_run_service = MagicMock(spec=RunService)
    window = MainWindow(service=service, run_service=mock_run_service)
    qtbot.addWidget(window)
    window.load_profiles()
    window._table.selectRow(0)

    # Mark profile as already running in UI
    assert prof.id is not None
    window._running_profile_ids.add(prof.id)
    window._on_selection_changed()

    # Sync buttons must be disabled when already running
    assert not window._action_sync.isEnabled()
    assert not window._action_dry_run.isEnabled()

    warning_shown = False

    def mock_warning(*args: object, **kwargs: object) -> QMessageBox.StandardButton:
        nonlocal warning_shown
        warning_shown = True
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", mock_warning)
    window._on_sync_now()
    assert warning_shown


def test_rclone_adapter_absorb_planned_and_cancel(tmp_path: Path) -> None:
    adapter = RcloneAdapter("rclone", tmp_path / "bisync")
    outcome = AdapterOutcome(returncode=0, command=[])

    # Stats event
    event1 = LogEvent(
        level="info",
        message="transfers",
        stats={"transfers": 5, "deletes": 2, "bytes": 1024, "speed": 512, "eta": 10},
    )
    adapter._absorb(event1, outcome)
    assert outcome.transfers == 5
    assert outcome.deletes == 2
    assert outcome.bytes_transferred == 1024
    assert outcome.speed == 512.0
    assert outcome.eta == 10

    # Dry-run copy event
    event2 = LogEvent(
        level="notice",
        message="Skipped copy as --dry-run is set",
        obj="doc.pdf",
    )
    adapter._absorb(event2, outcome)
    assert outcome.planned_copies == 1
    assert "doc.pdf" in outcome.planned_copy_files

    # Dry-run delete event
    event3 = LogEvent(
        level="notice",
        message="Skipped delete as --dry-run is set",
        obj="old.tmp",
    )
    adapter._absorb(event3, outcome)
    assert outcome.planned_deletes == 1
    assert "old.tmp" in outcome.planned_delete_files

    # Real run copy and delete events
    event4 = LogEvent(level="info", message="Copied (new)", obj="new.txt")
    event5 = LogEvent(level="info", message="Deleted", obj="removed.txt")
    adapter._absorb(event4, outcome)
    adapter._absorb(event5, outcome)
    assert "new.txt" in outcome.transferred_files
    assert "removed.txt" in outcome.deleted_files

    # Cancel when no process is running is a safe no-op
    adapter.cancel()


def test_send_notification_no_throw() -> None:
    # Does not crash in test environment
    send_notification("Test Title", "Test Message", is_error=False)
    send_notification("Error Title", "Error Message", is_error=True)


def test_sync_worker_with_real_sqlite_connection_no_thread_error(
    qtbot: QtBot, tmp_path: Path
) -> None:
    db_file = tmp_path / "thread_test.db"
    conn = connect(db_file, check_same_thread=False)
    profiles = ProfileRepository(conn)
    runs = RunRepository(conn)
    profile = profiles.add(_make_profile(tmp_path, "RealDbProfile", pid=1))

    mock_adapter = MagicMock(spec=RcloneAdapter)
    mock_adapter.needs_resync.return_value = False
    mock_adapter.run.return_value = AdapterOutcome(returncode=0, command=[], transfers=1)

    real_run_service = RunService(mock_adapter, runs, lock_dir=tmp_path / "locks")
    worker = SyncWorker(profile, real_run_service, dry_run=True)

    errors: list[str] = []
    worker.error_signal.connect(errors.append)

    with qtbot.waitSignal(worker.finished):
        worker.start()

    # Must finish without any SQLite thread errors
    assert len(errors) == 0
    persisted_runs = runs.list_for_profile(profile.id or 0)
    assert len(persisted_runs) == 1
    assert persisted_runs[0].status == RunStatus.SUCCESS
    conn.close()


def test_cloud_browser_shows_loading_indicator_and_loads_dirs(
    qtbot: QtBot,
) -> None:
    mock_remote_service = MagicMock(spec=RemoteService)
    from pontis.domain.models import RemoteInfo

    mock_remote_service.list_remotes.return_value = [RemoteInfo(name="gdrive", type="drive")]
    mock_remote_service.list_directories.return_value = ["Documents", "Photos", "Backups"]

    dialog = CloudFolderBrowserDialog(
        remote_service=mock_remote_service,
        initial_remote="gdrive",
        initial_path="",
    )
    qtbot.addWidget(dialog)

    assert dialog._folder_list.count() == 3
    assert dialog._folder_list.item(0).text() == "Documents"
    assert not dialog._lbl_status.isVisible()


def test_sync_progress_dialog_too_many_deletes_shows_force_button(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _make_profile(tmp_path)
    mock_run_service = MagicMock(spec=RunService)
    error_result = RunResult(
        profile_id=1, status=RunStatus.ERROR, message="Safety abort: too many deletes"
    )
    mock_run_service.run.return_value = error_result
    error_outcome = AdapterOutcome(
        returncode=1,
        command=["rclone"],
        is_too_many_deletes=True,
        error_messages=["Safety abort: too many deletes (>50%, 1 of 1)"],
    )
    mock_run_service.last_outcome = error_outcome

    dialog = SyncProgressDialog(profile, mock_run_service, dry_run=True)
    qtbot.addWidget(dialog)
    dialog.show()

    # Simulate finishing with too many deletes error
    dialog._on_finished(error_result, error_outcome)

    assert not dialog._btn_force.isHidden()
    status_text = dialog._status_label.text()
    assert (
        "Proteção de Segurança" in status_text
        or "Safety Protection" in status_text
        or "🛡️" in status_text
    )

    # User clicks force button
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    force_requested: list[bool] = []
    dialog.force_sync_requested.connect(force_requested.append)
    dialog._on_force_clicked()

    assert len(force_requested) == 1
    assert force_requested[0] is True  # is dry_run


def test_rclone_adapter_build_command_with_force(tmp_path: Path) -> None:
    adapter = RcloneAdapter("rclone", tmp_path / "state")
    profile = _make_profile(tmp_path)
    cmd_normal = adapter.build_command(profile, resync=False, force=False)
    cmd_forced = adapter.build_command(profile, resync=False, force=True)

    assert "--force" not in cmd_normal
    assert "--force" in cmd_forced


def test_run_service_auto_forces_when_deletes_within_safety_limit(tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    profile.options = SyncOptions(max_delete_files=25)
    mock_adapter = MagicMock(spec=RcloneAdapter)
    mock_adapter.needs_resync.return_value = False

    # First run aborts with 1 delete (e.g. rename)
    abort_outcome = AdapterOutcome(
        returncode=1,
        command=["rclone"],
        is_too_many_deletes=True,
        detected_deletes_count=1,
        error_messages=["Safety abort: too many deletes (>50%, 1 of 1)"],
    )
    # Second run with force succeeds
    success_outcome = AdapterOutcome(
        returncode=0,
        command=["rclone", "--force"],
        transfers=1,
        deletes=1,
    )
    mock_adapter.run.side_effect = [abort_outcome, success_outcome]

    conn = connect(tmp_path / "t.db")
    profile = ProfileRepository(conn).add(profile)
    run_repo = RunRepository(conn)
    service = RunService(mock_adapter, run_repo, tmp_path / "locks")

    result = service.run(profile, dry_run=False)

    assert result.status == RunStatus.SUCCESS
    assert mock_adapter.run.call_count == 2
    # Second call had force=True
    assert mock_adapter.run.call_args_list[1].kwargs["force"] is True


def test_run_service_stops_when_deletes_exceed_safety_limit(tmp_path: Path) -> None:
    profile = _make_profile(tmp_path)
    profile.options = SyncOptions(max_delete_files=25)
    mock_adapter = MagicMock(spec=RcloneAdapter)
    mock_adapter.needs_resync.return_value = False

    # Aborts with 30 deletes (> safety limit of 25)
    abort_outcome = AdapterOutcome(
        returncode=1,
        command=["rclone"],
        is_too_many_deletes=True,
        detected_deletes_count=30,
        error_messages=["Safety abort: too many deletes (>50%, 30 of 60)"],
    )
    mock_adapter.run.return_value = abort_outcome

    conn = connect(tmp_path / "t.db")
    profile = ProfileRepository(conn).add(profile)
    run_repo = RunRepository(conn)
    service = RunService(mock_adapter, run_repo, tmp_path / "locks")

    result = service.run(profile, dry_run=False)

    assert result.status == RunStatus.ERROR
    # Should NOT have auto-executed with force
    assert mock_adapter.run.call_count == 1
    assert service.last_outcome is not None
    assert service.last_outcome.is_too_many_deletes is True
