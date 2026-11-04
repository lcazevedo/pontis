# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for ScriptImporter and ProfileTransfer services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pontis.domain.models import (
    ConflictPolicy,
    EndpointKind,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.infra.database import connect
from pontis.infra.repositories import DuplicateProfileError
from pontis.services.import_export_service import (
    ProfileImportError,
    ProfileTransfer,
    ScriptImporter,
    ScriptImportError,
    _parse_endpoint_spec,
)
from pontis.services.profile_service import ProfileService

if TYPE_CHECKING:
    pass


def test_parse_real_sync_sh() -> None:
    """Ensure the user's sync.sh is parsed cleanly into a SyncProfile."""
    root_sync = Path("sync.sh")
    assert root_sync.is_file(), "Root sync.sh must exist."
    profile = ScriptImporter.parse_file(root_sync)

    assert profile.name == "SENAI"
    assert profile.side_a.kind == EndpointKind.LOCAL
    assert profile.side_a.path == "/home/lcazevedo/Documents/SENAI"
    assert profile.side_b.kind == EndpointKind.REMOTE
    assert profile.side_b.remote == "gdrive"
    assert profile.side_b.path == "SENAI"
    assert profile.options.direction == SyncDirection.BIDIRECTIONAL
    assert profile.options.conflict_policy == ConflictPolicy.NEWER
    assert profile.options.excludes == ("sync.sh", ".opencode/**", "**/node_modules/**")
    assert "--verbose" not in profile.options.extra_flags
    assert "--resync" not in profile.options.extra_flags


def test_parse_script_with_sync_and_options(tmp_path: Path) -> None:
    """Test parsing a unidirectional sync script with advanced flags."""
    script_content = """#!/bin/bash
SRC="/tmp/local_folder"
DST="myremote:backup/folder"

rclone sync "$SRC" "$DST" \\
  --exclude "*.bak" \\
  --include "*.pdf" \\
  --bwlimit 10M \\
  --transfers 8 \\
  --check-access \\
  --max-delete 50%
"""
    script_file = tmp_path / "backup.sh"
    script_file.write_text(script_content, encoding="utf-8")

    profile = ScriptImporter.parse_file(script_file)
    assert profile.name == "backup"
    assert profile.side_a.path == "/tmp/local_folder"
    assert profile.side_b.remote == "myremote"
    assert profile.side_b.path == "backup/folder"
    assert profile.options.direction == SyncDirection.A_TO_B
    assert profile.options.excludes == ("*.bak",)
    assert profile.options.includes == ("*.pdf",)
    assert profile.options.bandwidth_limit == "10M"
    assert profile.options.transfers == 8
    assert profile.options.check_access is True
    assert profile.options.max_delete_files == 50


def test_parse_script_errors(tmp_path: Path) -> None:
    """Test error handling on missing or invalid scripts."""
    missing = tmp_path / "nonexistent.sh"
    with pytest.raises(ScriptImportError, match="Script file not found"):
        ScriptImporter.parse_file(missing)

    invalid_content = "echo 'No rclone here'"
    with pytest.raises(ScriptImportError, match="No 'rclone bisync' or 'rclone sync'"):
        ScriptImporter.parse_text(invalid_content)

    no_args = "rclone bisync"
    with pytest.raises(ScriptImportError, match="requires two paths"):
        ScriptImporter.parse_text(no_args)


def test_profile_transfer_roundtrip(tmp_path: Path) -> None:
    """Test exporting profiles to JSON and reimporting them."""
    opt = SyncOptions(
        direction=SyncDirection.BIDIRECTIONAL,
        conflict_policy=ConflictPolicy.NEWER,
        excludes=("*.tmp", "node_modules/**"),
        bandwidth_limit="5M",
    )
    p1 = SyncProfile(
        name="Profile 1",
        side_a=_parse_endpoint_spec("/tmp/a"),
        side_b=_parse_endpoint_spec("gdrive:b"),
        options=opt,
    )
    p2 = SyncProfile(
        name="Profile 2",
        side_a=_parse_endpoint_spec("/tmp/c"),
        side_b=_parse_endpoint_spec("/tmp/d"),
    )

    out_file = tmp_path / "profiles.json"
    ProfileTransfer.export_to_file([p1, p2], out_file)
    assert out_file.is_file()

    imported = ProfileTransfer.import_from_file(out_file)
    assert len(imported) == 2
    assert imported[0].name == "Profile 1"
    assert imported[0].options.conflict_policy == ConflictPolicy.NEWER
    assert imported[0].options.excludes == ("*.tmp", "node_modules/**")
    assert imported[0].options.bandwidth_limit == "5M"
    assert imported[1].name == "Profile 2"
    assert imported[1].side_a.path == "/tmp/c"
    assert imported[1].side_b.path == "/tmp/d"


def test_profile_transfer_invalid_json(tmp_path: Path) -> None:
    """Test handling of corrupted or invalid JSON files."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(ProfileImportError, match="Invalid JSON format"):
        ProfileTransfer.import_from_file(bad_json)

    wrong_schema = tmp_path / "wrong.json"
    wrong_schema.write_text(json.dumps({"unknown": 123}), encoding="utf-8")
    with pytest.raises(ProfileImportError, match="Invalid data format"):
        ProfileTransfer.import_from_file(wrong_schema)


def test_profile_service_import_policies(tmp_path: Path) -> None:
    """Test ProfileService.import_profile with rename, overwrite, and raise policies."""
    conn = connect(tmp_path / "test_import.db")
    service = ProfileService(conn=conn)

    p1 = SyncProfile(
        name="SyncDocs",
        side_a=_parse_endpoint_spec("/tmp/docs"),
        side_b=_parse_endpoint_spec("remote:docs"),
    )
    saved1 = service.add_profile(p1)
    assert saved1.id is not None

    # 1. Rename policy (default)
    p_dup1 = SyncProfile(
        name="SyncDocs",
        side_a=_parse_endpoint_spec("/tmp/docs2"),
        side_b=_parse_endpoint_spec("remote:docs2"),
    )
    saved_dup1 = service.import_profile(p_dup1, on_conflict="rename")
    assert saved_dup1.name == "SyncDocs (1)"
    assert saved_dup1.id != saved1.id

    p_dup2 = SyncProfile(
        name="SyncDocs",
        side_a=_parse_endpoint_spec("/tmp/docs3"),
        side_b=_parse_endpoint_spec("remote:docs3"),
    )
    saved_dup2 = service.import_profile(p_dup2, on_conflict="rename")
    assert saved_dup2.name == "SyncDocs (2)"

    # 2. Overwrite policy
    p_update = SyncProfile(
        name="SyncDocs",
        side_a=_parse_endpoint_spec("/tmp/new_docs"),
        side_b=_parse_endpoint_spec("remote:new_docs"),
        options=SyncOptions(conflict_policy=ConflictPolicy.NEWER),
    )
    saved_overwrite = service.import_profile(p_update, on_conflict="overwrite")
    assert saved_overwrite.id == saved1.id
    assert saved_overwrite.side_a.path == "/tmp/new_docs"
    assert saved_overwrite.options.conflict_policy == ConflictPolicy.NEWER

    # 3. Raise policy
    p_raise = SyncProfile(
        name="SyncDocs",
        side_a=_parse_endpoint_spec("/tmp/docs"),
        side_b=_parse_endpoint_spec("remote:docs"),
    )
    with pytest.raises(DuplicateProfileError):
        service.import_profile(p_raise, on_conflict="raise")
