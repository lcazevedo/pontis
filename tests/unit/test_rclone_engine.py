# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the rclone engine: unit tests (no rclone) and local integration tests."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

import pytest

from pontis.cli import main as cli_main
from pontis.cli import parse_endpoint
from pontis.domain.models import (
    ConflictPolicy,
    Endpoint,
    RunStatus,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.infra.database import connect
from pontis.infra.locking import ProfileLock, ProfileLockedError
from pontis.infra.rclone import MIN_RCLONE_VERSION, locate_rclone, parse_version
from pontis.infra.rclone_adapter import RcloneAdapter, parse_log_line
from pontis.infra.repositories import ProfileRepository, RunRepository
from pontis.services.run_service import (
    EndpointMissingError,
    FirstRunDryRunRequiredError,
    RunService,
)

needs_rclone = pytest.mark.skipif(shutil.which("rclone") is None, reason="rclone not installed")


def make_profile(a: Path, b: Path, profile_id: int | None = 1, **opts: object) -> SyncProfile:
    return SyncProfile(
        "p",
        Endpoint.local(str(a)),
        Endpoint.local(str(b)),
        SyncOptions(**opts),  # type: ignore[arg-type]
        id=profile_id,
    )


# ---------------------------------------------------------------- unit tests


def test_parse_version() -> None:
    assert parse_version("rclone v1.75.0\n- os/version: x") == (1, 75, 0)
    assert parse_version("garbage") is None
    assert MIN_RCLONE_VERSION > (1, 65, 2)


def test_parse_log_line_strips_ansi_and_reads_stats() -> None:
    event = parse_log_line(
        '{"level":"info","msg":"\\u001b[32mok\\u001b[0m","stats":{"transfers":3}}'
    )
    assert event is not None
    assert event.message == "ok"
    assert event.stats == {"transfers": 3}
    assert parse_log_line("  ") is None
    plain = parse_log_line("not json")
    assert plain is not None
    assert plain.message == "not json"


def test_build_command_bidirectional_first_run(tmp_path: Path) -> None:
    adapter = RcloneAdapter("rclone", tmp_path / "state", tmp_path / "rclone.conf")
    profile = make_profile(
        tmp_path / "a",
        tmp_path / "b",
        conflict_policy=ConflictPolicy.NEWER,
        excludes=("sync.sh", "**/node_modules/**"),
        check_access=True,
        bandwidth_limit="1M",
        transfers=2,
    )
    cmd = adapter.build_command(profile, dry_run=True)
    assert cmd[:3] == ["rclone", "--config", str(tmp_path / "rclone.conf")]
    assert cmd[3:6] == ["bisync", str(tmp_path / "a"), str(tmp_path / "b")]
    assert "--resync" in cmd  # no listings yet
    assert cmd[cmd.index("--resync-mode") + 1] == "newer"
    assert "--max-delete" not in cmd  # resync never deletes
    assert "--dry-run" in cmd
    assert "--check-access" in cmd
    assert cmd.count("--exclude") == 2
    assert cmd[cmd.index("--bwlimit") + 1] == "1M"
    assert cmd[cmd.index("--transfers") + 1] == "2"
    assert "--drive-skip-gdocs" in cmd


def test_build_command_regular_run_uses_safety_flags(tmp_path: Path) -> None:
    adapter = RcloneAdapter("rclone", tmp_path / "state")
    profile = make_profile(
        tmp_path / "a", tmp_path / "b", conflict_policy=ConflictPolicy.NEWER, max_delete_percent=30
    )
    workdir = adapter.workdir(profile)
    workdir.mkdir(parents=True)
    (workdir / "x..y.path1.lst").write_text("")
    cmd = adapter.build_command(profile)
    assert "--resync" not in cmd
    assert cmd[cmd.index("--max-delete") + 1] == "30"
    assert cmd[cmd.index("--conflict-resolve") + 1] == "newer"
    assert "--config" not in cmd


def test_build_command_resync_only_when_requested(tmp_path: Path) -> None:
    adapter = RcloneAdapter("rclone", tmp_path / "state")
    profile = make_profile(tmp_path / "a", tmp_path / "b")
    assert "--resync" in adapter.build_command(profile, resync=True)
    assert "--resync" not in adapter.build_command(profile, resync=False)


def test_build_command_one_way(tmp_path: Path) -> None:
    adapter = RcloneAdapter("rclone", tmp_path / "state")
    profile = make_profile(tmp_path / "a", tmp_path / "b", direction=SyncDirection.B_TO_A)
    cmd = adapter.build_command(profile)
    assert cmd[1:4] == ["sync", str(tmp_path / "b"), str(tmp_path / "a")]
    assert not adapter.needs_resync(profile)


def test_forbidden_extra_flags_rejected(tmp_path: Path) -> None:
    adapter = RcloneAdapter("rclone", tmp_path / "state")
    profile = make_profile(tmp_path / "a", tmp_path / "b", extra_flags=("--resync",))
    with pytest.raises(ValueError, match="--resync"):
        adapter.build_command(profile)


def test_parse_endpoint() -> None:
    cloud = parse_endpoint("gdrive:SENAI")
    assert cloud.remote == "gdrive"
    assert cloud.path == "SENAI"
    assert parse_endpoint("/tmp/x").remote is None
    assert parse_endpoint("~/x").remote is None


def test_profile_lock_is_exclusive(tmp_path: Path) -> None:
    with ProfileLock(tmp_path, 7):
        with pytest.raises(ProfileLockedError):
            ProfileLock(tmp_path, 7).acquire()
        ProfileLock(tmp_path, 8).acquire()  # other profiles are independent
    other = ProfileLock(tmp_path, 7)
    other.acquire()  # released after the with block
    other.release()


def test_locate_rclone_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from pontis.infra import rclone as rclone_mod

    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setattr(rclone_mod, "app_rclone_path", lambda: tmp_path / "none")
    with pytest.raises(rclone_mod.RcloneNotFoundError):
        locate_rclone(tmp_path / "also-none")


# --------------------------------------------------- integration (local rclone)


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.a = tmp_path / "a"
        self.b = tmp_path / "b"
        self.a.mkdir()
        self.b.mkdir()
        self.conn = connect(tmp_path / "pontis.db")
        self.profiles = ProfileRepository(self.conn)
        self.runs = RunRepository(self.conn)
        info = locate_rclone()
        conf = tmp_path / "rclone.conf"
        conf.write_text("")
        self.adapter = RcloneAdapter(info.path, tmp_path / "bisync", conf)
        self.service = RunService(self.adapter, self.runs, tmp_path / "locks")
        self.profile = self.profiles.add(make_profile(self.a, self.b, profile_id=None))


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


@needs_rclone
def test_first_real_run_requires_dry_run(env: Env) -> None:
    (env.a / "x.txt").write_text("1")
    with pytest.raises(FirstRunDryRunRequiredError):
        env.service.run(env.profile)
    assert not (env.b / "x.txt").exists()


@needs_rclone
def test_dry_run_changes_nothing_and_keeps_first_run_state(env: Env) -> None:
    (env.a / "x.txt").write_text("1")
    result = env.service.run(env.profile, dry_run=True)
    assert result.status is RunStatus.SUCCESS
    assert result.dry_run
    assert not (env.b / "x.txt").exists()
    assert env.adapter.needs_resync(env.profile)


@needs_rclone
def test_bidirectional_sync_end_to_end(env: Env) -> None:
    (env.a / "from_a.txt").write_text("a")
    (env.b / "from_b.txt").write_text("b")
    env.service.run(env.profile, dry_run=True)
    first = env.service.run(env.profile)  # first run: automatic safe resync
    assert first.status is RunStatus.SUCCESS
    assert (env.b / "from_a.txt").read_text() == "a"
    assert (env.a / "from_b.txt").read_text() == "b"
    assert not env.adapter.needs_resync(env.profile)

    (env.a / "new_a.txt").write_text("n")
    (env.b / "from_b.txt").unlink()
    second = env.service.run(env.profile)
    assert second.status is RunStatus.SUCCESS
    assert (env.b / "new_a.txt").exists()
    assert not (env.a / "from_b.txt").exists()
    assert second.files_deleted == 1
    history = env.runs.list_for_profile(env.profile.id or 0)
    assert len(history) == 3


@needs_rclone
def test_max_delete_blocks_mass_deletion(env: Env) -> None:
    for i in range(10):
        (env.a / f"f{i}.txt").write_text(str(i))
    env.service.run(env.profile, dry_run=True)
    env.service.run(env.profile)
    for i in range(10):
        (env.b / f"f{i}.txt").unlink()
    result = env.service.run(env.profile)
    assert result.status is RunStatus.ERROR
    assert len(list(env.a.glob("f*.txt"))) == 10  # nothing was deleted


@needs_rclone
def test_excludes_are_respected(env: Env) -> None:
    env.profile.options = SyncOptions(excludes=("*.tmp",))
    env.profiles.update(env.profile)
    (env.a / "keep.txt").write_text("k")
    (env.a / "skip.tmp").write_text("s")
    env.service.run(env.profile, dry_run=True)
    env.service.run(env.profile)
    assert (env.b / "keep.txt").exists()
    assert not (env.b / "skip.tmp").exists()


@needs_rclone
def test_failed_run_never_adds_resync(env: Env) -> None:
    env.service.run(env.profile, dry_run=True)
    env.service.run(env.profile)
    shutil.rmtree(env.b)  # simulates an unmounted folder after the first sync
    with pytest.raises(EndpointMissingError):
        env.service.run(env.profile)
    assert "--resync" not in env.adapter.build_command(env.profile)


@needs_rclone
def test_locked_profile_is_refused(env: Env, tmp_path: Path) -> None:
    assert env.profile.id is not None
    with ProfileLock(tmp_path / "locks", env.profile.id), pytest.raises(ProfileLockedError):
        env.service.run(env.profile, dry_run=True)


@needs_rclone
def test_concurrent_run_in_thread_is_blocked(env: Env, tmp_path: Path) -> None:
    assert env.profile.id is not None
    started = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with ProfileLock(tmp_path / "locks", env.profile.id or 0):
            started.set()
            release.wait(5)

    t = threading.Thread(target=hold)
    t.start()
    started.wait(5)
    try:
        with pytest.raises(ProfileLockedError):
            env.service.run(env.profile, dry_run=True)
    finally:
        release.set()
        t.join()


@needs_rclone
def test_cli_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "one.txt").write_text("1")
    (b / "two.txt").write_text("2")
    db = str(tmp_path / "pontis.db")
    conf = tmp_path / "rclone.conf"
    conf.write_text("")
    base = ["--db", db]

    assert cli_main([*base, "profile", "add", "demo", "--a", str(a), "--b", str(b)]) == 0
    assert cli_main([*base, "profile", "add", "demo", "--a", str(a), "--b", str(b)]) == 1
    assert cli_main([*base, "profile", "list"]) == 0
    assert "demo" in capsys.readouterr().out

    run = [*base, "run", "demo", "--rclone-config", str(conf)]
    assert cli_main(run) == 4  # first real run needs a dry run
    assert cli_main([*run, "--dry-run"]) == 0
    assert not (b / "one.txt").exists()
    assert cli_main(run) == 0
    assert (b / "one.txt").exists()
    assert (a / "two.txt").exists()

    assert cli_main([*base, "profile", "remove", "demo"]) == 0
    assert cli_main([*base, "profile", "remove", "demo"]) == 1
    assert cli_main([*base, "run", "demo", "--rclone-config", str(conf)]) == 1
