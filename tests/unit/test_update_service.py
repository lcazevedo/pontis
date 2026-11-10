# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the release and update checking service."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from pontis.services.update_service import (
    UpdateCheckWorker,
    check_for_updates,
    is_newer_version,
    parse_version_tuple,
)


def test_parse_version_tuple() -> None:
    """Semantic version strings are converted to sortable tuples."""
    assert parse_version_tuple("v1.2.3") == (1, 2, 3, 1)
    assert parse_version_tuple("1.2") == (1, 2, 0, 1)
    assert parse_version_tuple("2") == (2, 0, 0, 1)
    assert parse_version_tuple("0.1.0.dev0") == (0, 1, 0, 0)
    assert parse_version_tuple("1.0.0-rc1") == (1, 0, 0, 0)
    assert parse_version_tuple("invalid") == (0, 0, 0, 0)


def test_is_newer_version() -> None:
    """Version comparison correctly detects updates."""
    assert is_newer_version(candidate="1.0.0", current="0.1.0")
    assert is_newer_version(candidate="1.0.1", current="1.0.0")
    assert is_newer_version(candidate="2.0.0", current="1.9.9")
    # Release candidate vs final
    assert is_newer_version(candidate="1.0.0", current="1.0.0-rc1")

    # Not newer
    assert not is_newer_version(candidate="0.1.0", current="0.1.0")
    assert not is_newer_version(candidate="0.1.0", current="1.0.0")
    assert not is_newer_version(candidate="1.0.0-rc1", current="1.0.0")


def test_check_for_updates_with_newer_release() -> None:
    """check_for_updates flags an update when a newer release is published."""
    mock_payload: dict[str, Any] = {
        "tag_name": "v1.2.0",
        "name": "Pontis 1.2.0 Release",
        "body": "## New Features\n* Added preferences dialog",
        "published_at": "2026-11-10T12:00:00Z",
        "html_url": "https://github.com/lcazevedo/pontis/releases/tag/v1.2.0",
    }

    with patch(
        "pontis.services.update_service.fetch_latest_release",
        return_value=mock_payload,
    ):
        info = check_for_updates(current_version="1.0.0")
        assert info.has_update is True
        assert info.latest_version == "1.2.0"
        assert info.current_version == "1.0.0"
        assert "New Features" in info.release_notes
        assert info.html_url.endswith("v1.2.0")


def test_check_for_updates_up_to_date() -> None:
    """check_for_updates marks has_update=False when current is latest."""
    mock_payload: dict[str, Any] = {
        "tag_name": "v1.0.0",
        "name": "Pontis 1.0.0",
        "body": "Current release",
        "published_at": "2026-10-30T10:00:00Z",
        "html_url": "https://github.com/lcazevedo/pontis/releases/tag/v1.0.0",
    }

    with patch(
        "pontis.services.update_service.fetch_latest_release",
        return_value=mock_payload,
    ):
        info = check_for_updates(current_version="1.0.0")
        assert info.has_update is False
        assert info.latest_version == "1.0.0"


def test_update_worker_emits_success(qtbot: Any) -> None:
    """UpdateCheckWorker runs asynchronously and emits finished_success."""
    mock_payload: dict[str, Any] = {
        "tag_name": "v1.5.0",
        "name": "Pontis 1.5.0",
        "body": "Changelog",
        "published_at": "2026-11-10T15:00:00Z",
        "html_url": "https://example.com/release",
    }

    with patch(
        "pontis.services.update_service.fetch_latest_release",
        return_value=mock_payload,
    ):
        worker = UpdateCheckWorker(current_version="1.0.0")
        with qtbot.waitSignal(worker.finished_success, timeout=3000) as blocker:
            worker.start()

        assert blocker.args[0].has_update is True
        assert blocker.args[0].latest_version == "1.5.0"
