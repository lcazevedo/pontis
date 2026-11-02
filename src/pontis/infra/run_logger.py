# SPDX-License-Identifier: GPL-3.0-or-later
"""Rotating execution logs management for sync runs."""

from __future__ import annotations

import shlex
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pontis.domain.models import RunStatus, utcnow
from pontis.infra.paths import log_dir as default_log_dir

if TYPE_CHECKING:
    from pontis.infra.rclone_adapter import LogEvent


class RunLogWriter:
    """Writes formatted events to a specific run log file."""

    def __init__(
        self,
        file_path: Path,
        run_id: int,
        profile_name: str,
        dry_run: bool,
        command: list[str],
    ) -> None:
        self.file_path = file_path
        self.run_id = run_id
        self.profile_name = profile_name
        self.dry_run = dry_run
        self.command = list(command)
        self._lines: list[str] = []
        self._init_header()

    def _init_header(self) -> None:
        mode_str = "Simulation (Dry Run)" if self.dry_run else "Real Sync"
        cmd_str = shlex.join(self.command) if self.command else "N/A"
        header = [
            "=" * 60,
            "Pontis Sync Execution Log",
            f"Run ID:       {self.run_id}",
            f"Profile:      {self.profile_name}",
            f"Mode:         {mode_str}",
            f"Started At:   {utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Command:      {cmd_str}",
            "=" * 60,
            "",
        ]
        self._lines.extend(header)
        self._flush()

    def write_event(self, event: LogEvent) -> None:
        """Format and append a parsed rclone log event."""
        if not event.message.strip():
            return
        level_tag = f"[{event.level.upper():<7}]"
        obj_tag = f" ({event.obj})" if event.obj else ""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {level_tag}{obj_tag} {event.message}"
        self._lines.append(line)
        self._flush()

    def write_raw_line(self, line: str) -> None:
        """Append an unformatted raw line."""
        text = line.rstrip()
        if text:
            ts = datetime.now().strftime("%H:%M:%S")
            self._lines.append(f"[{ts}] {text}")
            self._flush()

    def finish(
        self,
        status: RunStatus,
        files_transferred: int,
        files_deleted: int,
        errors: int,
        message: str = "",
    ) -> None:
        """Write summary footer and flush to disk."""
        footer = [
            "",
            "=" * 60,
            "Execution Summary",
            f"Finished At:  {utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Final Status: {status.value.upper()}",
            f"Transferred:  {files_transferred}",
            f"Deleted:      {files_deleted}",
            f"Errors:       {errors}",
        ]
        if message:
            footer.append(f"Message:      {message}")
        footer.extend(["=" * 60, ""])
        self._lines.extend(footer)
        self._flush()

    def _flush(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(self._lines) + "\n"
        self.file_path.write_text(content, encoding="utf-8")


class RunLogManager:
    """Manages creation, rotation, reading, and export of run logs."""

    def __init__(
        self,
        log_dir: Path | None = None,
        max_files: int = 100,
        max_size_mb: int = 50,
    ) -> None:
        root = log_dir if log_dir is not None else default_log_dir()
        self._runs_dir = root / "runs"
        self._max_files = max(1, max_files)
        self._max_size_bytes = max(1, max_size_mb) * 1024 * 1024

    @property
    def runs_dir(self) -> Path:
        """Directory where run log files are stored."""
        return self._runs_dir

    def log_path_for_run(self, run_id: int) -> Path:
        """Return the expected log file path for a given run ID."""
        return self._runs_dir / f"run_{run_id}.log"

    def create_writer(
        self,
        run_id: int,
        profile_name: str,
        *,
        dry_run: bool,
        command: list[str],
    ) -> RunLogWriter:
        """Instantiate a log writer for an active run."""
        path = self.log_path_for_run(run_id)
        return RunLogWriter(
            file_path=path,
            run_id=run_id,
            profile_name=profile_name,
            dry_run=dry_run,
            command=command,
        )

    def get_run_log(self, run_id: int) -> str:
        """Read the full content of a run log file or return empty if missing."""
        path = self.log_path_for_run(run_id)
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def export_log(self, run_id: int, target_path: Path) -> None:
        """Export the run log to the target path."""
        content = self.get_run_log(run_id)
        if not content:
            content = f"No execution log found for run #{run_id}.\n"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

    def prune_logs(self) -> int:
        """Prune old run logs according to count and size limits.

        Returns the number of pruned log files.
        """
        if not self._runs_dir.is_dir():
            return 0

        log_files = sorted(
            self._runs_dir.glob("run_*.log"),
            key=lambda p: (p.stat().st_mtime, p.name),
        )
        if not log_files:
            return 0

        deleted_count = 0

        # Prune if exceeding file count limit
        while len(log_files) > self._max_files:
            oldest = log_files.pop(0)
            try:
                oldest.unlink(missing_ok=True)
                deleted_count += 1
            except OSError:
                pass

        # Prune if exceeding total size limit
        total_size = sum(f.stat().st_size for f in log_files if f.is_file())
        while total_size > self._max_size_bytes and log_files:
            oldest = log_files.pop(0)
            try:
                sz = oldest.stat().st_size if oldest.is_file() else 0
                oldest.unlink(missing_ok=True)
                total_size -= sz
                deleted_count += 1
            except OSError:
                pass

        return deleted_count

    def delete_log(self, run_id: int) -> bool:
        """Delete a single run log file."""
        path = self.log_path_for_run(run_id)
        if path.is_file():
            try:
                path.unlink(missing_ok=True)
                return True
            except OSError:
                return False
        return False

    def delete_logs_for_runs(self, run_ids: list[int]) -> int:
        """Delete log files for the specified run IDs."""
        count = 0
        for rid in run_ids:
            if self.delete_log(rid):
                count += 1
        return count
