# SPDX-License-Identifier: GPL-3.0-or-later
"""Release checking and update notification service for Pontis."""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError

from PySide6.QtCore import QThread, Signal

from pontis import __version__ as APP_VERSION
from pontis.links import GITHUB_REPO

logger = logging.getLogger(__name__)

DEFAULT_REPO = GITHUB_REPO
GITHUB_API_RELEASES_URL = "https://api.github.com/repos/{repo}/releases/latest"

_VERSION_CLEAN_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(.*)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    """Information regarding an application release."""

    has_update: bool
    current_version: str
    latest_version: str
    release_name: str
    release_notes: str
    release_url: str
    published_at: str
    html_url: str
    tag_name: str


def parse_version_tuple(version_str: str) -> tuple[int, int, int, int]:
    """Parse a version string into a comparable 4-element tuple (major, minor, patch, dev_flag).

    Pre-release or dev versions get a lower weight (0) than release versions (1).
    """
    cleaned = version_str.strip().lstrip("v")
    match = _VERSION_CLEAN_RE.match(cleaned)
    if not match:
        return (0, 0, 0, 0)

    major_str, minor_str, patch_str, suffix = match.groups()
    major = int(major_str) if major_str is not None else 0
    minor = int(minor_str) if minor_str is not None else 0
    patch = int(patch_str) if patch_str is not None else 0

    suffix_lower = (suffix or "").lower()
    is_dev_or_rc = any(tag in suffix_lower for tag in ("dev", "rc", "alpha", "beta", "a", "b"))
    tag_weight = 0 if is_dev_or_rc else 1

    return (major, minor, patch, tag_weight)


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    """Return True if candidate is strictly newer than current version."""
    candidate_tuple = parse_version_tuple(candidate)
    current_tuple = parse_version_tuple(current)
    return candidate_tuple > current_tuple


class UpdateCheckError(Exception):
    """Raised when an update check fails."""


def fetch_latest_release(
    repo: str = DEFAULT_REPO,
    timeout: float = 5.0,
    api_url: str | None = None,
) -> dict[str, Any]:
    """Fetch the latest release payload from GitHub."""
    target_url = api_url or GITHUB_API_RELEASES_URL.format(repo=repo)
    headers = {
        "User-Agent": f"Pontis-App/{APP_VERSION}",
        "Accept": "application/vnd.github.v3+json",
    }
    req = urllib.request.Request(target_url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return payload
    except HTTPError as exc:
        raise UpdateCheckError(f"HTTP Error {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise UpdateCheckError(f"Network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise UpdateCheckError("Connection timed out while checking for updates.") from exc
    except Exception as exc:
        raise UpdateCheckError(f"Failed to check for updates: {exc}") from exc


def check_for_updates(
    repo: str = DEFAULT_REPO,
    current_version: str = APP_VERSION,
    timeout: float = 5.0,
    api_url: str | None = None,
) -> UpdateInfo:
    """Check for updates against the GitHub releases API."""
    data = fetch_latest_release(repo=repo, timeout=timeout, api_url=api_url)

    tag_name = str(data.get("tag_name", "")).strip()
    latest_version = tag_name.lstrip("v") or tag_name
    release_name = str(data.get("name", "")).strip() or tag_name
    release_notes = str(data.get("body", "")).strip()
    published_at = str(data.get("published_at", "")).strip()
    html_url = str(data.get("html_url", "")).strip()

    newer = is_newer_version(candidate=latest_version, current=current_version)

    return UpdateInfo(
        has_update=newer,
        current_version=current_version,
        latest_version=latest_version,
        release_name=release_name,
        release_notes=release_notes,
        release_url=html_url,
        published_at=published_at,
        html_url=html_url,
        tag_name=tag_name,
    )


class UpdateCheckWorker(QThread):
    """Background worker for asynchronous update checks."""

    finished_success = Signal(object)  # UpdateInfo
    finished_error = Signal(str)

    def __init__(
        self,
        repo: str = DEFAULT_REPO,
        current_version: str = APP_VERSION,
        timeout: float = 5.0,
        api_url: str | None = None,
    ) -> None:
        super().__init__()
        self._repo = repo
        self._current_version = current_version
        self._timeout = timeout
        self._api_url = api_url

    def run(self) -> None:
        """Execute the HTTP check on a secondary thread."""
        try:
            info = check_for_updates(
                repo=self._repo,
                current_version=self._current_version,
                timeout=self._timeout,
                api_url=self._api_url,
            )
            self.finished_success.emit(info)
        except Exception as exc:
            logger.debug("Update check failed: %s", exc)
            self.finished_error.emit(str(exc))
