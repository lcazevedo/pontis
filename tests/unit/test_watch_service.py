# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the WatchService and ProfileWatchHandler."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from pontis.domain.models import Endpoint, SyncOptions, SyncProfile
from pontis.services.watch_service import (
    ProfileWatchError,
    ProfileWatchHandler,
    WatchService,
)


@dataclass
class _DummyEvent:
    event_type: str
    src_path: str
    is_directory: bool = False


def test_handler_filtering_and_debounce(tmp_path: Path) -> None:
    """Test that ignored patterns are filtered and valid events trigger sync after debounce."""
    base_dir = tmp_path / "watched"
    base_dir.mkdir()

    opts = SyncOptions(excludes=("*.log", "ignored_dir/**"))
    profile = SyncProfile(
        name="TestWatch",
        side_a=Endpoint.local(str(base_dir)),
        side_b=Endpoint.cloud("remote", "folder"),
        options=opts,
    )

    changes: list[tuple[str, str]] = []
    syncs: list[SyncProfile] = []

    handler = ProfileWatchHandler(
        profile=profile,
        base_dir=base_dir,
        debounce_seconds=0.1,  # Fast debounce for test
        on_change=lambda etype, path: changes.append((etype, path)),
        on_sync_triggered=lambda p: syncs.append(p),
    )

    try:
        # 1. Ignored system files (.git, .tmp, bisync listings)
        handler.dispatch(_DummyEvent("modified", str(base_dir / ".git" / "HEAD")))
        handler.dispatch(_DummyEvent("created", str(base_dir / "test.tmp")))
        handler.dispatch(_DummyEvent("modified", str(base_dir / ".rclone-bisync.lst")))
        # 2. Ignored by profile exclude (*.log, ignored_dir/**)
        handler.dispatch(_DummyEvent("modified", str(base_dir / "app.log")))
        handler.dispatch(_DummyEvent("created", str(base_dir / "ignored_dir" / "file.txt")))
        # 3. Directory events should be ignored
        handler.dispatch(_DummyEvent("modified", str(base_dir / "subfolder"), is_directory=True))

        assert len(changes) == 0
        time.sleep(0.15)
        assert len(syncs) == 0

        # 4. Valid file events
        valid_file1 = base_dir / "document.txt"
        valid_file2 = base_dir / "notes.md"
        handler.dispatch(_DummyEvent("modified", str(valid_file1)))
        assert len(changes) == 1

        # Rapid subsequent modification within debounce period
        time.sleep(0.04)
        handler.dispatch(_DummyEvent("created", str(valid_file2)))
        assert len(changes) == 2

        # Wait for debounce to expire
        time.sleep(0.15)
        assert len(syncs) == 1
        assert syncs[0].name == "TestWatch"
    finally:
        handler.stop()


def test_watch_service_get_watchable_paths(tmp_path: Path) -> None:
    """Test path discovery and validation in WatchService."""
    local_dir = tmp_path / "valid_local"
    local_dir.mkdir()

    # 1. Profile with existing local path
    p_local = SyncProfile(
        name="LocalProfile",
        side_a=Endpoint.local(str(local_dir)),
        side_b=Endpoint.cloud("remote", "path"),
    )
    paths = WatchService.get_watchable_paths(p_local)
    assert len(paths) == 1
    assert paths[0] == local_dir.resolve()

    # 2. Profile with cloud-only endpoints
    p_cloud = SyncProfile(
        name="CloudProfile",
        side_a=Endpoint.cloud("rem1", "path1"),
        side_b=Endpoint.cloud("rem2", "path2"),
    )
    assert len(WatchService.get_watchable_paths(p_cloud)) == 0

    watch_service = WatchService()
    with pytest.raises(ProfileWatchError, match="no accessible local folder"):
        watch_service.start_watching(p_cloud)


def test_watch_service_start_and_stop(tmp_path: Path) -> None:
    """Test starting and stopping real observers."""
    local_dir = tmp_path / "watch_target"
    local_dir.mkdir()

    profile = SyncProfile(
        name="WatchMe",
        side_a=Endpoint.local(str(local_dir)),
        side_b=Endpoint.cloud("rem", "path"),
        id=99,
    )

    service = WatchService()
    try:
        watched = service.start_watching(profile, debounce_seconds=1.0)
        assert len(watched) == 1
        assert service.is_watching(99)

        # Stop specific
        stopped = service.stop_watching(99)
        assert stopped is True
        assert not service.is_watching(99)
    finally:
        service.stop_all()
