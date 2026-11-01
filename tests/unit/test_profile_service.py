# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for ProfileService."""

from __future__ import annotations

from pathlib import Path

import pytest

from pontis.domain.models import (
    Endpoint,
    RunResult,
    RunStatus,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.infra.database import connect
from pontis.infra.repositories import ProfileNotFoundError
from pontis.services.profile_service import ProfileService


@pytest.fixture
def temp_service(tmp_path: Path) -> ProfileService:
    db_path = tmp_path / "test_profiles.db"
    conn = connect(db_path)
    return ProfileService(conn=conn)


def test_empty_service(temp_service: ProfileService) -> None:
    assert temp_service.list_profiles() == []
    assert temp_service.list_summaries() == []


def test_add_and_get_profile(temp_service: ProfileService) -> None:
    p = SyncProfile(
        name="DocsSync",
        side_a=Endpoint.local("/tmp/a"),
        side_b=Endpoint.cloud("drive", "backup"),
        options=SyncOptions(direction=SyncDirection.BIDIRECTIONAL),
    )
    created = temp_service.add_profile(p)
    assert created.id is not None

    found = temp_service.get_profile(created.id)
    assert found.name == "DocsSync"
    assert found.side_a.path == "/tmp/a"
    assert found.side_b.remote == "drive"

    by_name = temp_service.get_profile_by_name("DocsSync")
    assert by_name is not None
    assert by_name.id == created.id


def test_list_summaries_with_last_run(temp_service: ProfileService) -> None:
    p = temp_service.add_profile(
        SyncProfile(
            name="Photos",
            side_a=Endpoint.local("/tmp/photos"),
            side_b=Endpoint.local("/tmp/photos_backup"),
        )
    )
    assert p.id is not None

    # Before any run
    summaries = temp_service.list_summaries()
    assert len(summaries) == 1
    assert summaries[0].profile.name == "Photos"
    assert summaries[0].last_run is None

    # After adding a run result
    run = RunResult(
        profile_id=p.id,
        status=RunStatus.SUCCESS,
        files_transferred=42,
    )
    temp_service._run_repo.add(run)

    summaries = temp_service.list_summaries()
    assert len(summaries) == 1
    assert summaries[0].last_run is not None
    assert summaries[0].last_run.status == RunStatus.SUCCESS
    assert summaries[0].last_run.files_transferred == 42


def test_delete_profile(temp_service: ProfileService) -> None:
    p = temp_service.add_profile(
        SyncProfile(
            name="ToDelete",
            side_a=Endpoint.local("/tmp/del1"),
            side_b=Endpoint.local("/tmp/del2"),
        )
    )
    assert p.id is not None

    temp_service.delete_profile(p.id)
    assert temp_service.list_profiles() == []
    assert temp_service.get_profile_by_name("ToDelete") is None

    with pytest.raises(ProfileNotFoundError):
        temp_service.get_profile(p.id)
