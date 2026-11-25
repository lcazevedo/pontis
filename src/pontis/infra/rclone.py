# SPDX-License-Identifier: GPL-3.0-or-later
"""Locating the rclone binary and checking its version."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pontis.infra.paths import data_dir

MIN_RCLONE_VERSION: tuple[int, int, int] = (1, 66, 0)
"""Oldest rclone release with the bisync features Pontis relies on."""

_VERSION_RE = re.compile(r"rclone\s+v?(\d+)\.(\d+)\.(\d+)")


class RcloneError(Exception):
    """Base class for rclone discovery problems."""


class RcloneNotFoundError(RcloneError):
    """Raised when no usable rclone binary can be found."""


class RcloneTooOldError(RcloneError):
    """Raised when the rclone binary is older than :data:`MIN_RCLONE_VERSION`."""

    def __init__(self, found: tuple[int, int, int], minimum: tuple[int, int, int]) -> None:
        super().__init__(format_version(found))
        self.found = found
        self.minimum = minimum


@dataclass(frozen=True, slots=True)
class RcloneInfo:
    """A validated rclone installation."""

    path: Path
    version: tuple[int, int, int]
    source: str  # "configured", "app" or "path"


def format_version(version: tuple[int, int, int]) -> str:
    """Format a version tuple as ``1.66.0``."""
    return ".".join(str(p) for p in version)


def parse_version(output: str) -> tuple[int, int, int] | None:
    """Extract the version from ``rclone version`` output, or ``None``."""
    match = _VERSION_RE.search(output)
    if match is None:
        return None
    major, minor, patch = (int(g) for g in match.groups())
    return major, minor, patch


def app_rclone_path() -> Path:
    """Location where an app-managed rclone would live (not shipped in v1)."""
    return data_dir() / "bin" / "rclone"


def clean_subprocess_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a subprocess environment safe from PyInstaller's ``LD_LIBRARY_PATH``.

    When running from a frozen PyInstaller bundle, restore ``LD_LIBRARY_PATH_ORIG``
    or unset ``LD_LIBRARY_PATH`` so external binaries like ``rclone`` do not load
    bundled libraries incompatible with the host system.
    """
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        if "LD_LIBRARY_PATH_ORIG" in env:
            env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
        else:
            env.pop("LD_LIBRARY_PATH", None)
    if extra:
        env.update(extra)
    return env


def read_version(binary: Path) -> tuple[int, int, int]:
    """Run ``<binary> version`` and return its version."""
    try:
        proc = subprocess.run(
            [str(binary), "version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=clean_subprocess_env(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RcloneNotFoundError(str(binary)) from exc
    version = parse_version(proc.stdout)
    if version is None:
        raise RcloneNotFoundError(str(binary))
    return version


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def locate_rclone(configured: Path | str | None = None) -> RcloneInfo:
    """Find rclone: configured path, then the app's own copy, then ``PATH``.

    Raises :class:`RcloneNotFoundError` when none works and
    :class:`RcloneTooOldError` when the first one found is below the minimum version.
    """
    candidates: list[tuple[str, Path]] = []
    if configured:
        candidates.append(("configured", Path(configured).expanduser()))
    candidates.append(("app", app_rclone_path()))
    on_path = shutil.which("rclone")
    if on_path:
        candidates.append(("path", Path(on_path)))

    for source, path in candidates:
        if not _executable(path):
            continue
        version = read_version(path)
        if version < MIN_RCLONE_VERSION:
            raise RcloneTooOldError(version, MIN_RCLONE_VERSION)
        return RcloneInfo(path=path, version=version, source=source)
    raise RcloneNotFoundError("rclone")
