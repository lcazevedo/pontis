# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for domain models, migrations and repositories."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pontis.domain import (
    ConflictPolicy,
    Endpoint,
    RunResult,
    RunStatus,
    ScheduleKind,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.infra import database
from pontis.infra.repositories import (
    DuplicateProfileError,
    ProfileNotFoundError,
    ProfileRepository,
    RunRepository,
)


@pytest.fixture
def conn() -> sqlite3.Connection:
    return database.connect(":memory:")


def make_profile(name: str = "Docs") -> SyncProfile:
    return SyncProfile(
        name=name,
        side_a=Endpoint.local("/tmp/a"),
        side_b=Endpoint.cloud("gdrive", "PontisTeste"),
        options=SyncOptions(
            direction=SyncDirection.BIDIRECTIONAL,
            conflict_policy=ConflictPolicy.NEWER,
            excludes=("*.tmp", ".git/**"),
            transfers=4,
        ),
    )


def test_endpoint_validation_and_rclone_string() -> None:
    assert Endpoint.cloud("gdrive", "x/y").to_rclone() == "gdrive:x/y"
    assert Endpoint.local("/tmp/a").to_rclone() == "/tmp/a"
    with pytest.raises(ValueError):
        Endpoint.local("")
    with pytest.raises(ValueError):
        Endpoint.cloud("", "x")


def test_options_validation_and_roundtrip() -> None:
    with pytest.raises(ValueError):
        SyncOptions(max_delete_files=-1)
    with pytest.raises(ValueError):
        SyncOptions(transfers=0)
    opts = make_profile().options
    assert SyncOptions.from_dict(opts.to_dict()) == opts
    assert SyncOptions.from_dict({}) == SyncOptions()


def test_profile_requires_name() -> None:
    with pytest.raises(ValueError):
        SyncProfile(name="  ", side_a=Endpoint.local("/a"), side_b=Endpoint.local("/b"))


def test_migrations_set_version_and_are_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    c1 = database.connect(db)
    assert database.schema_version(c1) == database.LATEST_VERSION
    c1.close()
    c2 = database.connect(db)
    assert database.schema_version(c2) == database.LATEST_VERSION
    tables = {r[0] for r in c2.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"profiles", "runs"} <= tables


def test_newer_schema_is_rejected(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    raw = sqlite3.connect(db)
    raw.execute(f"PRAGMA user_version = {database.LATEST_VERSION + 1}")
    raw.close()
    with pytest.raises(RuntimeError):
        database.connect(db)


def test_profile_crud(conn: sqlite3.Connection) -> None:
    repo = ProfileRepository(conn)
    p = repo.add(make_profile())
    assert p.id is not None

    loaded = repo.get(p.id)
    assert loaded.name == "Docs"
    assert loaded.side_b == Endpoint.cloud("gdrive", "PontisTeste")
    assert loaded.options == p.options
    assert loaded.schedule.kind is ScheduleKind.MANUAL
    assert loaded.created_at == p.created_at

    loaded.name = "Docs2"
    loaded.options = SyncOptions(max_delete_percent=10)
    repo.update(loaded)
    again = repo.get(p.id)
    assert again.name == "Docs2"
    assert again.options.max_delete_percent == 10
    assert again.updated_at >= p.updated_at

    assert [x.name for x in repo.list()] == ["Docs2"]
    assert repo.get_by_name("Docs2") is not None
    assert repo.get_by_name("nope") is None

    repo.delete(p.id)
    assert repo.list() == []
    with pytest.raises(ProfileNotFoundError):
        repo.get(p.id)
    with pytest.raises(ProfileNotFoundError):
        repo.delete(p.id)


def test_duplicate_name_rejected(conn: sqlite3.Connection) -> None:
    repo = ProfileRepository(conn)
    repo.add(make_profile("A"))
    with pytest.raises(DuplicateProfileError):
        repo.add(make_profile("A"))
    other = repo.add(make_profile("B"))
    other.name = "A"
    with pytest.raises(DuplicateProfileError):
        repo.update(other)


def test_null_schedule_means_manual(conn: sqlite3.Connection) -> None:
    repo = ProfileRepository(conn)
    p = repo.add(make_profile())
    conn.execute("UPDATE profiles SET schedule = NULL")
    assert p.id is not None
    assert repo.get(p.id).schedule.kind is ScheduleKind.MANUAL


def test_run_history_and_cascade(conn: sqlite3.Connection) -> None:
    profiles = ProfileRepository(conn)
    runs = RunRepository(conn)
    p = profiles.add(make_profile())
    assert p.id is not None

    r1 = runs.add(RunResult(profile_id=p.id, dry_run=True))
    r2 = runs.add(RunResult(profile_id=p.id))
    r2.status = RunStatus.SUCCESS
    r2.files_transferred = 3
    r2.finished_at = r2.started_at
    runs.update(r2)

    assert r1.id is not None and r2.id is not None
    got = runs.get(r2.id)
    assert got is not None
    assert got.status is RunStatus.SUCCESS and got.files_transferred == 3
    first = runs.get(r1.id)
    assert first is not None and first.dry_run
    assert [r.id for r in runs.list_for_profile(p.id)] == [r2.id, r1.id]
    last = runs.last_for_profile(p.id)
    assert last is not None and last.id == r2.id
    assert len(runs.list_for_profile(p.id, limit=1)) == 1

    profiles.delete(p.id)
    assert runs.list_for_profile(p.id) == []
