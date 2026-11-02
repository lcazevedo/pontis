# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for run logs, rotation, history repositories, and ProfileService history APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from pontis.domain.models import (
    Endpoint,
    RunResult,
    RunStatus,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.infra.database import connect
from pontis.infra.rclone_adapter import AdapterOutcome, LogEvent
from pontis.infra.repositories import ProfileRepository, RunRepository
from pontis.infra.run_logger import RunLogManager
from pontis.services.profile_service import ProfileService
from pontis.services.run_service import RunService

if TYPE_CHECKING:
    from pathlib import Path


def _make_profile(pid: int = 1, name: str = "TestProfile") -> SyncProfile:
    return SyncProfile(
        id=pid,
        name=name,
        side_a=Endpoint.local("/tmp/a"),
        side_b=Endpoint.local("/tmp/b"),
        options=SyncOptions(direction=SyncDirection.BIDIRECTIONAL),
    )


def test_run_log_writer_and_reader(tmp_path: Path) -> None:
    log_mgr = RunLogManager(log_dir=tmp_path)
    writer = log_mgr.create_writer(
        run_id=42,
        profile_name="BackupDocs",
        dry_run=False,
        command=["rclone", "bisync", "/tmp/a", "/tmp/b"],
    )

    writer.write_event(LogEvent(level="info", message="Bisyncing Path1 with Path2"))
    writer.write_event(
        LogEvent(level="warning", message="New or changed in both paths", obj="test.txt")
    )
    writer.finish(
        status=RunStatus.SUCCESS,
        files_transferred=5,
        files_deleted=0,
        errors=0,
        message="Completed successfully",
    )

    log_text = log_mgr.get_run_log(42)
    assert "Pontis Sync Execution Log" in log_text
    assert "Run ID:       42" in log_text
    assert "Profile:      BackupDocs" in log_text
    assert "Bisyncing Path1 with Path2" in log_text
    assert "New or changed in both paths" in log_text
    assert "test.txt" in log_text
    assert "Final Status: SUCCESS" in log_text
    assert "Transferred:  5" in log_text

    # Test export
    export_path = tmp_path / "exports" / "run_42_export.txt"
    log_mgr.export_log(42, export_path)
    assert export_path.is_file()
    assert export_path.read_text(encoding="utf-8") == log_text


def test_run_log_rotation_pruning(tmp_path: Path) -> None:
    log_mgr = RunLogManager(log_dir=tmp_path, max_files=3, max_size_mb=1)

    # Create 5 log files with different run IDs
    for rid in range(1, 6):
        w = log_mgr.create_writer(rid, f"Profile{rid}", dry_run=False, command=["test"])
        w.write_raw_line(f"Log content for run #{rid}")
        w.finish(RunStatus.SUCCESS, 1, 0, 0)

    # Before pruning, 5 files exist
    assert len(list(log_mgr.runs_dir.glob("run_*.log"))) == 5

    pruned = log_mgr.prune_logs()
    assert pruned == 2
    remaining = sorted(f.name for f in log_mgr.runs_dir.glob("run_*.log"))
    assert len(remaining) == 3
    # Oldest runs (1 and 2) were pruned, leaving 3, 4, 5
    assert "run_4.log" in remaining
    assert "run_5.log" in remaining


def test_run_repository_queries_and_deletion(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    p_repo = ProfileRepository(conn)
    r_repo = RunRepository(conn)

    p1 = p_repo.add(
        SyncProfile(name="Profile1", side_a=Endpoint.local("/a"), side_b=Endpoint.local("/b"))
    )
    p2 = p_repo.add(
        SyncProfile(name="Profile2", side_a=Endpoint.local("/c"), side_b=Endpoint.local("/d"))
    )
    assert p1.id is not None and p2.id is not None

    r1 = r_repo.add(RunResult(profile_id=p1.id, status=RunStatus.SUCCESS, files_transferred=10))
    r_repo.add(RunResult(profile_id=p1.id, status=RunStatus.ERROR, errors=1))
    r_repo.add(RunResult(profile_id=p2.id, status=RunStatus.CANCELLED, dry_run=True))

    # Test list_all
    all_runs = r_repo.list_all()
    assert len(all_runs) == 3
    # Check limit
    limited = r_repo.list_all(limit=2)
    assert len(limited) == 2

    # Test delete single run
    assert r1.id is not None
    assert r_repo.delete(r1.id) is True
    assert r_repo.get(r1.id) is None
    assert len(r_repo.list_all()) == 2

    # Test delete_for_profile
    deleted_p1 = r_repo.delete_for_profile(p1.id)
    assert deleted_p1 == 1
    assert len(r_repo.list_for_profile(p1.id)) == 0
    assert len(r_repo.list_for_profile(p2.id)) == 1

    # Test clear_all
    cleared = r_repo.clear_all()
    assert cleared == 1
    assert len(r_repo.list_all()) == 0


def test_profile_service_history_integration(tmp_path: Path) -> None:
    db_file = tmp_path / "pontis.db"
    service = ProfileService(db_path=db_file)
    log_dir = tmp_path / "logs"

    p = service.add_profile(
        SyncProfile(name="TestP", side_a=Endpoint.local("/a"), side_b=Endpoint.local("/b"))
    )
    assert p.id is not None

    conn = service.connection
    r_repo = RunRepository(conn)
    r = r_repo.add(RunResult(profile_id=p.id, status=RunStatus.SUCCESS, files_transferred=3))
    assert r.id is not None

    # Write a log file using RunLogManager pointing to log_dir
    log_mgr = RunLogManager(log_dir=log_dir)
    writer = log_mgr.create_writer(r.id, p.name, dry_run=False, command=["rclone"])
    writer.write_raw_line("Custom test line")
    writer.finish(RunStatus.SUCCESS, 3, 0, 0)

    # Test service.list_runs
    runs = service.list_runs(profile_id=p.id)
    assert len(runs) == 1
    assert runs[0].id == r.id

    # Test service.get_run_log
    log_content = service.get_run_log(r.id, log_dir=log_dir)
    assert "Custom test line" in log_content

    # Test service.export_run_log
    export_target = tmp_path / "exported.log"
    service.export_run_log(r.id, export_target, log_dir=log_dir)
    assert export_target.is_file()
    assert "Custom test line" in export_target.read_text(encoding="utf-8")

    # Test delete_run removes run and its log
    assert service.delete_run(r.id) is True
    assert len(service.list_runs()) == 0
    service.close()


def test_run_service_writes_log_during_execution(tmp_path: Path) -> None:
    conn = connect(":memory:")
    runs = RunRepository(conn)
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    log_mgr = RunLogManager(log_dir=tmp_path / "logs")

    side_a = tmp_path / "side_a"
    side_b = tmp_path / "side_b"
    side_a.mkdir()
    side_b.mkdir()

    p_repo = ProfileRepository(conn)
    profile = p_repo.add(
        SyncProfile(
            name="AutoLogProfile",
            side_a=Endpoint.local(str(side_a)),
            side_b=Endpoint.local(str(side_b)),
        )
    )

    adapter = MagicMock()
    adapter.needs_resync.return_value = False
    adapter.build_command.return_value = ["rclone", "bisync", str(side_a), str(side_b)]

    def mock_run(prof: SyncProfile, **kwargs: object) -> AdapterOutcome:
        cb = kwargs.get("on_event")
        if callable(cb):
            cb(LogEvent(level="info", message="Listing directories..."))
            cb(LogEvent(level="notice", message="Copied 2 files"))
        return AdapterOutcome(
            returncode=0,
            command=["rclone"],
            transfers=2,
            deletes=0,
            errors=0,
        )

    adapter.run.side_effect = mock_run

    service = RunService(adapter, runs, lock_dir=lock_dir, log_manager=log_mgr)
    result = service.run(profile, dry_run=False, require_dry_run_first=False)
    assert result.status == RunStatus.SUCCESS
    assert result.id is not None

    log_text = log_mgr.get_run_log(result.id)
    assert "Listing directories..." in log_text
    assert "Copied 2 files" in log_text
    assert "Final Status: SUCCESS" in log_text
