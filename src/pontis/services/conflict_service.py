# SPDX-License-Identifier: GPL-3.0-or-later
"""Conflict detection and resolution service for Pontis sync profiles."""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pontis.domain.models import EndpointKind, SyncProfile

if TYPE_CHECKING:
    from pontis.domain.models import Endpoint


class ConflictResolution(StrEnum):
    """Action to resolve a conflicted file pair."""

    KEEP_SIDE_A = "keep_side_a"
    KEEP_SIDE_B = "keep_side_b"
    KEEP_BOTH = "keep_both"
    DELETE_BOTH = "delete_both"


@dataclass(slots=True)
class ConflictFileInfo:
    """Information about one side's conflicted file."""

    name: str
    relative_path: str
    endpoint_path: str
    size: int
    modified: datetime | None = None
    side: str = "side_a"
    preview: str = ""


@dataclass(slots=True)
class ConflictItem:
    """A detected conflict between two versions of a base file."""

    base_name: str
    side_a_file: ConflictFileInfo | None = None
    side_b_file: ConflictFileInfo | None = None


_CONFLICT_PATTERN = re.compile(r"^(.*?)\.conflict([12])$")


def _read_preview(path: Path, max_lines: int = 15) -> str:
    """Read first few lines of a local text file for preview."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = [f.readline() for _ in range(max_lines)]
            return "".join(lines)
    except Exception:
        return ""


def _split_stem_suffix(filename: str) -> tuple[str, str]:
    """Split filename into base stem and extension suffix."""
    p = Path(filename)
    return p.stem, p.suffix


class ConflictService:
    """Detects conflicted files and applies user resolution choices."""

    def __init__(
        self,
        rclone_binary: Path | str = "rclone",
        config_path: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._binary = str(rclone_binary)
        self._config_path = config_path
        self._env = dict(env) if env is not None else None

    def scan_conflicts(self, profile: SyncProfile) -> list[ConflictItem]:
        """Scan profile endpoints for conflict files (*.conflict1, *.conflict2)."""
        conflicts_map: dict[str, ConflictItem] = {}

        # Scan Side A
        self._scan_endpoint(profile.side_a, "side_a", conflicts_map)
        # Scan Side B
        self._scan_endpoint(profile.side_b, "side_b", conflicts_map)

        return sorted(conflicts_map.values(), key=lambda c: c.base_name)

    def _scan_endpoint(
        self,
        endpoint: Endpoint,
        side_tag: str,
        conflicts_map: dict[str, ConflictItem],
    ) -> None:
        """Scan a single endpoint (local or remote) for conflict files."""
        if endpoint.kind is EndpointKind.LOCAL:
            local_root = Path(endpoint.path).expanduser()
            if not local_root.is_dir():
                return
            for root, _, files in os.walk(local_root):
                for fname in files:
                    m = _CONFLICT_PATTERN.match(fname)
                    if not m:
                        continue
                    full_p = Path(root) / fname
                    rel_p = str(full_p.relative_to(local_root))
                    parent_p = Path(rel_p).parent
                    base_rel = str(parent_p / m.group(1)) if parent_p != Path(".") else m.group(1)
                    try:
                        stat = full_p.stat()
                        size = stat.st_size
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                    except OSError:
                        size = 0
                        mtime = None

                    preview = _read_preview(full_p) if size < 1_000_000 else ""
                    c_info = ConflictFileInfo(
                        name=fname,
                        relative_path=rel_p,
                        endpoint_path=str(full_p),
                        size=size,
                        modified=mtime,
                        side=side_tag,
                        preview=preview,
                    )
                    which_side = "side_a" if m.group(2) == "1" else "side_b"
                    item = conflicts_map.setdefault(base_rel, ConflictItem(base_name=base_rel))
                    if which_side == "side_a":
                        item.side_a_file = c_info
                    else:
                        item.side_b_file = c_info
        else:
            # Remote endpoint via rclone
            remote_target = endpoint.to_rclone()
            cmd = [
                self._binary,
                "lsf",
                remote_target,
                "--recursive",
                "--files-only",
                "--format",
                "pst",
                "--include",
                "*.conflict*",
                "--drive-skip-gdocs",
            ]
            if self._config_path:
                cmd += ["--config", str(self._config_path)]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    env=self._env,
                    timeout=30,
                )
                if proc.returncode != 0:
                    return
                for line in proc.stdout.splitlines():
                    line = line.strip()
                    if not line or ";" not in line:
                        continue
                    parts = line.split(";")
                    # format pst: path;size;time
                    if len(parts) >= 2:
                        rel_path = parts[0]
                        fname = Path(rel_path).name
                        m = _CONFLICT_PATTERN.match(fname)
                        if not m:
                            continue
                        try:
                            size = int(parts[1]) if parts[1] else 0
                        except ValueError:
                            size = 0
                        mtime = None
                        if len(parts) >= 3 and parts[2]:
                            with contextlib.suppress(ValueError):
                                mtime = datetime.fromisoformat(parts[2].replace("Z", "+00:00"))
                        parent_p = Path(rel_path).parent
                        base_rel = (
                            str(parent_p / m.group(1)) if parent_p != Path(".") else m.group(1)
                        )
                        full_remote = f"{remote_target}/{rel_path}"
                        c_info = ConflictFileInfo(
                            name=fname,
                            relative_path=rel_path,
                            endpoint_path=full_remote,
                            size=size,
                            modified=mtime,
                            side=side_tag,
                        )
                        which_side = "side_a" if m.group(2) == "1" else "side_b"
                        item = conflicts_map.setdefault(base_rel, ConflictItem(base_name=base_rel))
                        if which_side == "side_a":
                            item.side_a_file = c_info
                        else:
                            item.side_b_file = c_info
            except Exception:
                return

    def resolve_conflict(
        self,
        profile: SyncProfile,
        conflict: ConflictItem,
        resolution: ConflictResolution,
    ) -> bool:
        """Apply a resolution choice to the given conflicted file pair."""
        success = True
        base_name = conflict.base_name

        # Resolve on local endpoints first (instantly)
        for ep in (profile.side_a, profile.side_b):
            if ep.kind is EndpointKind.LOCAL:
                if not self._resolve_local(Path(ep.path).expanduser(), base_name, resolution):
                    success = False
            else:
                if not self._resolve_remote(ep, base_name, resolution):
                    success = False

        return success

    def _resolve_local(
        self,
        root: Path,
        base_rel: str,
        resolution: ConflictResolution,
    ) -> bool:
        """Resolve conflict on a local filesystem directory."""
        target = root / base_rel
        c1 = root / f"{base_rel}.conflict1"
        c2 = root / f"{base_rel}.conflict2"

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if resolution == ConflictResolution.KEEP_SIDE_A:
                if c1.is_file():
                    c1.replace(target)
                if c2.is_file():
                    c2.unlink(missing_ok=True)
            elif resolution == ConflictResolution.KEEP_SIDE_B:
                if c2.is_file():
                    c2.replace(target)
                if c1.is_file():
                    c1.unlink(missing_ok=True)
            elif resolution == ConflictResolution.KEEP_BOTH:
                stem, suffix = _split_stem_suffix(target.name)
                parent = target.parent
                new_a = parent / f"{stem} (Side A){suffix}"
                new_b = parent / f"{stem} (Side B){suffix}"
                if c1.is_file():
                    c1.replace(new_a)
                if c2.is_file():
                    c2.replace(new_b)
            elif resolution == ConflictResolution.DELETE_BOTH:
                c1.unlink(missing_ok=True)
                c2.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def _resolve_remote(
        self,
        endpoint: Endpoint,
        base_rel: str,
        resolution: ConflictResolution,
    ) -> bool:
        """Resolve conflict on a remote cloud endpoint via rclone commands."""
        remote_root = endpoint.to_rclone()
        target_path = f"{remote_root}/{base_rel}"
        c1_path = f"{remote_root}/{base_rel}.conflict1"
        c2_path = f"{remote_root}/{base_rel}.conflict2"

        def _rclone_run(*args: str) -> bool:
            cmd = [self._binary, *args]
            if self._config_path:
                cmd += ["--config", str(self._config_path)]
            try:
                res = subprocess.run(cmd, capture_output=True, env=self._env, timeout=30)
                return res.returncode == 0
            except Exception:
                return False

        if resolution == ConflictResolution.KEEP_SIDE_A:
            _rclone_run("moveto", c1_path, target_path)
            _rclone_run("deletefile", c2_path)
        elif resolution == ConflictResolution.KEEP_SIDE_B:
            _rclone_run("moveto", c2_path, target_path)
            _rclone_run("deletefile", c1_path)
        elif resolution == ConflictResolution.KEEP_BOTH:
            stem, suffix = _split_stem_suffix(Path(base_rel).name)
            parent = str(Path(base_rel).parent)
            prefix = f"{remote_root}/{parent}/" if parent != "." else f"{remote_root}/"
            new_a = f"{prefix}{stem} (Side A){suffix}"
            new_b = f"{prefix}{stem} (Side B){suffix}"
            _rclone_run("moveto", c1_path, new_a)
            _rclone_run("moveto", c2_path, new_b)
        elif resolution == ConflictResolution.DELETE_BOTH:
            _rclone_run("deletefile", c1_path)
            _rclone_run("deletefile", c2_path)

        return True

    def resolve_all(
        self,
        profile: SyncProfile,
        resolutions: dict[str, ConflictResolution],
    ) -> dict[str, bool]:
        """Apply a batch of resolutions keyed by base_name."""
        conflicts = {c.base_name: c for c in self.scan_conflicts(profile)}
        results: dict[str, bool] = {}
        for base_name, action in resolutions.items():
            if base_name in conflicts:
                results[base_name] = self.resolve_conflict(profile, conflicts[base_name], action)
        return results
