# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds and runs rclone commands for a sync profile."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pontis.domain.models import ConflictPolicy, SyncDirection, SyncProfile

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

FORBIDDEN_EXTRA_FLAGS: frozenset[str] = frozenset(
    {
        "--resync",
        "--resync-mode",
        "--force",
        "--config",
        "--workdir",
        "--max-delete",
        "--dry-run",
        "-n",
        "--use-json-log",
        "--log-file",
        "--remove-empty-dirs",
    }
)
"""Flags the app controls itself; users may not pass them as free-form flags."""

_CONFLICT_ARGS: dict[ConflictPolicy, str] = {
    ConflictPolicy.KEEP_BOTH: "none",
    ConflictPolicy.NEWER: "newer",
    ConflictPolicy.LARGER: "larger",
    ConflictPolicy.PATH1: "path1",
    ConflictPolicy.PATH2: "path2",
}


@dataclass(frozen=True, slots=True)
class LogEvent:
    """One parsed line of rclone's ``--use-json-log`` output."""

    level: str
    message: str
    obj: str | None = None
    stats: dict[str, Any] | None = None
    raw: str = ""


@dataclass(slots=True)
class AdapterOutcome:
    """Result of one rclone process."""

    returncode: int
    command: list[str]
    transfers: int = 0
    deletes: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)
    needs_resync: bool = False
    planned_copies: int = 0
    planned_deletes: int = 0


EventCallback = Callable[[LogEvent], None]


def parse_log_line(line: str) -> LogEvent | None:
    """Parse one JSON log line; return ``None`` for blank or non-JSON lines."""
    text = line.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return LogEvent(level="info", message=_ANSI_RE.sub("", text), raw=line)
    if not isinstance(data, dict):
        return None
    stats = data.get("stats")
    return LogEvent(
        level=str(data.get("level", "info")),
        message=_ANSI_RE.sub("", str(data.get("msg", ""))),
        obj=data.get("object"),
        stats=stats if isinstance(stats, dict) else None,
        raw=line,
    )


def check_extra_flag(flag: str) -> str | None:
    """Check a single flag. Returns an error message if invalid, or None if valid."""
    cleaned = flag.strip()
    if not cleaned:
        return None
    if not cleaned.startswith("-"):
        return f"Flag must start with '-' or '--': '{cleaned}'"
    name = cleaned.split("=", 1)[0]
    if name in FORBIDDEN_EXTRA_FLAGS:
        return f"Flag '{name}' is managed by Pontis and cannot be added manually."
    return None


def validate_extra_flags(flags: tuple[str, ...]) -> None:
    """Reject free-form flags that the app manages itself or that have invalid formats."""
    for flag in flags:
        err = check_extra_flag(flag)
        if err is not None:
            raise ValueError(err)


class RcloneAdapter:
    """Translates a :class:`SyncProfile` into rclone invocations.

    Bidirectional profiles use ``rclone bisync`` with a per-profile working
    directory (so the app knows whether the first ``--resync`` is still needed).
    One-way profiles use ``rclone sync``.
    """

    def __init__(
        self,
        binary: Path | str,
        state_root: Path,
        config_path: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._binary = str(binary)
        self._state_root = state_root
        self._config_path = config_path
        self._env = dict(env) if env is not None else None

    def workdir(self, profile: SyncProfile) -> Path:
        """Bisync state directory of a profile."""
        pid = profile.id if profile.id is not None else "<profile-id>"
        return self._state_root / str(pid)

    def needs_resync(self, profile: SyncProfile) -> bool:
        """True when bisync has no saved listings yet (first run)."""
        if profile.options.direction is not SyncDirection.BIDIRECTIONAL:
            return False
        if profile.id is None:
            return True
        workdir = self.workdir(profile)
        return not (workdir.is_dir() and any(workdir.glob("*.lst")))

    def build_command(
        self,
        profile: SyncProfile,
        *,
        dry_run: bool = False,
        resync: bool | None = None,
    ) -> list[str]:
        """Build the full rclone command line.

        ``resync=None`` decides automatically from the saved state. A resync is
        never added by anything other than first-run detection or an explicit
        ``resync=True``.
        """
        opts = profile.options
        validate_extra_flags(opts.extra_flags)
        a = profile.side_a.to_rclone()
        b = profile.side_b.to_rclone()
        cmd = [self._binary]
        if self._config_path is not None:
            cmd += ["--config", str(self._config_path)]

        if opts.direction is SyncDirection.BIDIRECTIONAL:
            cmd += ["bisync", a, b, "--workdir", str(self.workdir(profile))]
            do_resync = self.needs_resync(profile) if resync is None else resync
            if do_resync:
                cmd += ["--resync", "--resync-mode", "newer"]
            else:
                cmd += [
                    "--conflict-resolve",
                    _CONFLICT_ARGS[opts.conflict_policy],
                    "--max-delete",
                    str(opts.max_delete_percent),
                ]
            if opts.check_access:
                cmd.append("--check-access")
        else:
            src, dst = (a, b) if opts.direction is SyncDirection.A_TO_B else (b, a)
            cmd += ["sync", src, dst]

        for pattern in opts.includes:
            cmd += ["--include", pattern]
        for pattern in opts.excludes:
            cmd += ["--exclude", pattern]
        if opts.bandwidth_limit:
            cmd += ["--bwlimit", opts.bandwidth_limit]
        if opts.transfers is not None:
            cmd += ["--transfers", str(opts.transfers)]
        cmd += list(opts.extra_flags)
        cmd += ["--use-json-log", "-v", "--stats", "1s"]
        if dry_run:
            cmd.append("--dry-run")
        return cmd

    def run(
        self,
        profile: SyncProfile,
        *,
        dry_run: bool = False,
        on_event: EventCallback | None = None,
    ) -> AdapterOutcome:
        """Run rclone for the profile, streaming parsed log events to ``on_event``.

        Does not retry or escalate to ``--resync`` on failure. On
        ``KeyboardInterrupt`` the child process is terminated and the
        exception propagates.
        """
        if profile.id is None:
            raise ValueError("Profile must be saved before running.")
        command = self.build_command(profile, dry_run=dry_run)
        if profile.options.direction is SyncDirection.BIDIRECTIONAL:
            self.workdir(profile).mkdir(parents=True, exist_ok=True)
        outcome = AdapterOutcome(returncode=-1, command=command)
        proc = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            env=self._env,
        )
        assert proc.stderr is not None
        try:
            for line in proc.stderr:
                event = parse_log_line(line)
                if event is None:
                    continue
                self._absorb(event, outcome)
                if on_event is not None:
                    on_event(event)
            outcome.returncode = proc.wait()
        except BaseException:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            raise
        return outcome

    @staticmethod
    def _absorb(event: LogEvent, outcome: AdapterOutcome) -> None:
        if event.stats is not None:
            outcome.transfers = int(event.stats.get("transfers", 0))
            outcome.deletes = int(event.stats.get("deletes", 0))
            outcome.errors = int(event.stats.get("errors", 0))
        if event.level in ("error", "critical") and event.message:
            outcome.error_messages.append(event.message)
            if "Must run --resync" in event.message:
                outcome.needs_resync = True
