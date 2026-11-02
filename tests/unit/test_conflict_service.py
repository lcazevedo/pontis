# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for conflict detection, preview and resolution logic."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from pontis.domain.models import Endpoint, SyncDirection, SyncOptions, SyncProfile
from pontis.services.conflict_service import (
    ConflictResolution,
    ConflictService,
)

needs_rclone = pytest.mark.skipif(shutil.which("rclone") is None, reason="rclone not installed")

if TYPE_CHECKING:
    from pathlib import Path


def _make_profile(side_a_dir: Path, side_b_dir: Path, name: str = "ConfProfile") -> SyncProfile:
    return SyncProfile(
        id=1,
        name=name,
        side_a=Endpoint.local(str(side_a_dir)),
        side_b=Endpoint.local(str(side_b_dir)),
        options=SyncOptions(direction=SyncDirection.BIDIRECTIONAL),
    )


def test_conflict_scanning_and_preview(tmp_path: Path) -> None:
    side_a = tmp_path / "side_a"
    side_b = tmp_path / "side_b"
    side_a.mkdir()
    side_b.mkdir()

    # Create conflicted pair for notes.txt
    (side_a / "notes.txt.conflict1").write_text("Notes version from Side A", encoding="utf-8")
    (side_a / "notes.txt.conflict2").write_text("Notes version from Side B", encoding="utf-8")

    # Create conflicted pair in a subdirectory
    sub_a = side_a / "sub"
    sub_a.mkdir()
    (sub_a / "code.py.conflict1").write_text("print('code A')", encoding="utf-8")
    (sub_a / "code.py.conflict2").write_text("print('code B')", encoding="utf-8")

    profile = _make_profile(side_a, side_b)
    service = ConflictService()
    conflicts = service.scan_conflicts(profile)

    assert len(conflicts) == 2
    base_names = [c.base_name for c in conflicts]
    assert "notes.txt" in base_names
    assert "sub/code.py" in base_names

    notes_item = next(c for c in conflicts if c.base_name == "notes.txt")
    assert notes_item.side_a_file is not None
    assert notes_item.side_b_file is not None
    assert "Notes version from Side A" in notes_item.side_a_file.preview
    assert "Notes version from Side B" in notes_item.side_b_file.preview


def test_resolve_conflict_keep_side_a(tmp_path: Path) -> None:
    side_a = tmp_path / "side_a"
    side_b = tmp_path / "side_b"
    side_a.mkdir()
    side_b.mkdir()

    (side_a / "data.csv.conflict1").write_text("col1,col2\na1,a2", encoding="utf-8")
    (side_a / "data.csv.conflict2").write_text("col1,col2\nb1,b2", encoding="utf-8")
    (side_b / "data.csv.conflict1").write_text("col1,col2\na1,a2", encoding="utf-8")
    (side_b / "data.csv.conflict2").write_text("col1,col2\nb1,b2", encoding="utf-8")

    profile = _make_profile(side_a, side_b)
    service = ConflictService()
    conflicts = service.scan_conflicts(profile)
    assert len(conflicts) == 1

    ok = service.resolve_conflict(profile, conflicts[0], ConflictResolution.KEEP_SIDE_A)
    assert ok is True

    # Check Side A
    assert (side_a / "data.csv").is_file()
    assert (side_a / "data.csv").read_text(encoding="utf-8") == "col1,col2\na1,a2"
    assert not (side_a / "data.csv.conflict1").exists()
    assert not (side_a / "data.csv.conflict2").exists()

    # Check Side B
    assert (side_b / "data.csv").is_file()
    assert (side_b / "data.csv").read_text(encoding="utf-8") == "col1,col2\na1,a2"
    assert not (side_b / "data.csv.conflict1").exists()
    assert not (side_b / "data.csv.conflict2").exists()

    # Re-scan must report 0 conflicts
    assert len(service.scan_conflicts(profile)) == 0


def test_resolve_conflict_keep_side_b(tmp_path: Path) -> None:
    side_a = tmp_path / "side_a"
    side_b = tmp_path / "side_b"
    side_a.mkdir()
    side_b.mkdir()

    (side_a / "report.txt.conflict1").write_text("Content A", encoding="utf-8")
    (side_a / "report.txt.conflict2").write_text("Content B", encoding="utf-8")

    profile = _make_profile(side_a, side_b)
    service = ConflictService()
    conflicts = service.scan_conflicts(profile)
    assert len(conflicts) == 1

    ok = service.resolve_conflict(profile, conflicts[0], ConflictResolution.KEEP_SIDE_B)
    assert ok is True

    assert (side_a / "report.txt").is_file()
    assert (side_a / "report.txt").read_text(encoding="utf-8") == "Content B"
    assert not (side_a / "report.txt.conflict1").exists()
    assert not (side_a / "report.txt.conflict2").exists()


def test_resolve_conflict_keep_both(tmp_path: Path) -> None:
    side_a = tmp_path / "side_a"
    side_b = tmp_path / "side_b"
    side_a.mkdir()
    side_b.mkdir()

    (side_a / "image.png.conflict1").write_text("bytes_A", encoding="utf-8")
    (side_a / "image.png.conflict2").write_text("bytes_B", encoding="utf-8")

    profile = _make_profile(side_a, side_b)
    service = ConflictService()
    conflicts = service.scan_conflicts(profile)

    ok = service.resolve_conflict(profile, conflicts[0], ConflictResolution.KEEP_BOTH)
    assert ok is True

    assert (side_a / "image (Side A).png").is_file()
    assert (side_a / "image (Side B).png").is_file()
    assert not (side_a / "image.png.conflict1").exists()
    assert not (side_a / "image.png.conflict2").exists()
    assert len(service.scan_conflicts(profile)) == 0


def test_resolve_conflict_delete_both(tmp_path: Path) -> None:
    side_a = tmp_path / "side_a"
    side_b = tmp_path / "side_b"
    side_a.mkdir()
    side_b.mkdir()

    (side_a / "junk.tmp.conflict1").write_text("trash1", encoding="utf-8")
    (side_a / "junk.tmp.conflict2").write_text("trash2", encoding="utf-8")

    profile = _make_profile(side_a, side_b)
    service = ConflictService()
    conflicts = service.scan_conflicts(profile)

    ok = service.resolve_conflict(profile, conflicts[0], ConflictResolution.DELETE_BOTH)
    assert ok is True
    assert not (side_a / "junk.tmp.conflict1").exists()
    assert not (side_a / "junk.tmp.conflict2").exists()
    assert len(service.scan_conflicts(profile)) == 0


def test_conflict_resolve_all_batch(tmp_path: Path) -> None:
    side_a = tmp_path / "side_a"
    side_b = tmp_path / "side_b"
    side_a.mkdir()
    side_b.mkdir()

    (side_a / "f1.txt.conflict1").write_text("1A", encoding="utf-8")
    (side_a / "f1.txt.conflict2").write_text("1B", encoding="utf-8")
    (side_a / "f2.txt.conflict1").write_text("2A", encoding="utf-8")
    (side_a / "f2.txt.conflict2").write_text("2B", encoding="utf-8")

    profile = _make_profile(side_a, side_b)
    service = ConflictService()

    resolutions = {
        "f1.txt": ConflictResolution.KEEP_SIDE_A,
        "f2.txt": ConflictResolution.KEEP_SIDE_B,
    }
    results = service.resolve_all(profile, resolutions)
    assert results["f1.txt"] is True
    assert results["f2.txt"] is True

    assert (side_a / "f1.txt").read_text(encoding="utf-8") == "1A"
    assert (side_a / "f2.txt").read_text(encoding="utf-8") == "2B"
    assert len(service.scan_conflicts(profile)) == 0


def test_bisync_error_needs_resync_detection() -> None:
    from pontis.infra.rclone_adapter import AdapterOutcome, LogEvent, RcloneAdapter

    outcome = AdapterOutcome(returncode=1, command=["rclone", "bisync"])
    event1 = LogEvent(
        level="error",
        message="Bisync aborted. Must run --resync to recover.",
    )
    RcloneAdapter._absorb(event1, outcome)
    assert outcome.needs_resync is True

    # Test conflict detection from events
    outcome2 = AdapterOutcome(returncode=0, command=["rclone", "bisync"])
    event2 = LogEvent(
        level="notice",
        message="- WARNING  New or changed in both paths       - mydoc.docx",
    )
    RcloneAdapter._absorb(event2, outcome2)
    assert outcome2.has_conflicts is True
    assert "mydoc.docx" in outcome2.conflicts_detected


@needs_rclone
def test_end_to_end_conflict_resolution_and_history(tmp_path: Path) -> None:
    from pontis.infra.database import connect
    from pontis.infra.rclone import locate_rclone
    from pontis.infra.rclone_adapter import RcloneAdapter
    from pontis.infra.repositories import ProfileRepository, RunRepository
    from pontis.infra.run_logger import RunLogManager
    from pontis.services.profile_service import ProfileService
    from pontis.services.run_service import RunService

    rclone_path = locate_rclone().path
    db_file = tmp_path / "app.db"
    conn = connect(db_file)
    p_repo = ProfileRepository(conn)
    r_repo = RunRepository(conn)

    side_a = tmp_path / "dir_a"
    side_b = tmp_path / "dir_b"
    side_a.mkdir()
    side_b.mkdir()

    # Pre-create test file
    (side_a / "notes.txt").write_text("Original content", encoding="utf-8")

    profile = p_repo.add(
        SyncProfile(
            name="E2EConflictProfile",
            side_a=Endpoint.local(str(side_a)),
            side_b=Endpoint.local(str(side_b)),
            options=SyncOptions(direction=SyncDirection.BIDIRECTIONAL),
        )
    )
    assert profile.id is not None

    adapter = RcloneAdapter(rclone_path, state_root=tmp_path / "bisync")
    lock_dir = tmp_path / "locks"
    log_dir = tmp_path / "logs"
    log_mgr = RunLogManager(log_dir=log_dir)
    run_service = RunService(adapter, r_repo, lock_dir=lock_dir, log_manager=log_mgr)

    # 1. Initial sync (resync)
    run1 = run_service.run(profile, dry_run=False, require_dry_run_first=False)
    assert run1.status.value == "success"
    assert (side_b / "notes.txt").read_text(encoding="utf-8") == "Original content"

    # 2. Provoke conflict by editing both sides
    (side_a / "notes.txt").write_text("Version edited on A", encoding="utf-8")
    (side_b / "notes.txt").write_text("Version edited on B", encoding="utf-8")

    # 3. Run sync (bisync with keep_both)
    run2 = run_service.run(profile, dry_run=False, force=True, require_dry_run_first=False)
    assert run2.status.value == "success"
    assert run_service.last_outcome is not None
    assert run_service.last_outcome.has_conflicts is True
    assert "notes.txt" in run_service.last_outcome.conflicts_detected

    # 4. Scan conflicts via ConflictService
    conflict_service = ConflictService(rclone_binary=rclone_path)
    conflicts = conflict_service.scan_conflicts(profile)
    assert len(conflicts) == 1
    assert conflicts[0].base_name == "notes.txt"

    # 5. Resolve conflict: choose to KEEP_SIDE_A
    ok = conflict_service.resolve_conflict(profile, conflicts[0], ConflictResolution.KEEP_SIDE_A)
    assert ok is True
    assert (side_a / "notes.txt").read_text(encoding="utf-8") == "Version edited on A"
    assert not (side_a / "notes.txt.conflict1").exists()
    assert not (side_a / "notes.txt.conflict2").exists()

    # 6. Run sync again to consolidate
    run3 = run_service.run(profile, dry_run=False, force=True, require_dry_run_first=False)
    assert run3.status.value == "success"
    assert (side_b / "notes.txt").read_text(encoding="utf-8") == "Version edited on A"

    # 7. Check history and execution logs via ProfileService
    prof_svc = ProfileService(conn=conn)
    history = prof_svc.list_runs(profile.id)
    assert len(history) == 3

    # Check that execution logs exist and can be read/exported
    log1 = prof_svc.get_run_log(run1.id, log_dir=log_dir)  # type: ignore[arg-type]
    log2 = prof_svc.get_run_log(run2.id, log_dir=log_dir)  # type: ignore[arg-type]
    log3 = prof_svc.get_run_log(run3.id, log_dir=log_dir)  # type: ignore[arg-type]
    assert "Pontis Sync Execution Log" in log1
    assert "New or changed in both paths" in log2
    assert "Final Status: SUCCESS" in log3

    export_path = tmp_path / "run2.log"
    prof_svc.export_run_log(run2.id, export_path, log_dir=log_dir)  # type: ignore[arg-type]
    assert export_path.is_file()
    assert "New or changed in both paths" in export_path.read_text(encoding="utf-8")
