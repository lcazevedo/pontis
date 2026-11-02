# SPDX-License-Identifier: GPL-3.0-or-later
"""Profile service: coordinates sync profile storage and run summary queries."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pontis.domain.models import RunResult, SyncProfile
from pontis.infra.database import connect
from pontis.infra.paths import default_db_path
from pontis.infra.repositories import ProfileRepository, RunRepository
from pontis.infra.run_logger import RunLogManager


@dataclass(slots=True)
class ProfileSummary:
    """A sync profile combined with its latest execution result, if any."""

    profile: SyncProfile
    last_run: RunResult | None = None


class ProfileService:
    """Application service for managing sync profiles and querying execution status."""

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        db_path: Path | None = None,
    ) -> None:
        self._owned_conn = False
        if conn is None:
            self._conn = connect(db_path or default_db_path())
            self._owned_conn = True
        else:
            self._conn = conn

        self._profile_repo = ProfileRepository(self._conn)
        self._run_repo = RunRepository(self._conn)

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the underlying SQLite connection."""
        return self._conn

    def list_profiles(self) -> list[SyncProfile]:
        """Return all sync profiles ordered by name."""
        return self._profile_repo.list()

    def list_summaries(self) -> list[ProfileSummary]:
        """Return all profiles paired with their most recent run result."""
        profiles = self._profile_repo.list()
        summaries: list[ProfileSummary] = []
        for profile in profiles:
            last_run = (
                self._run_repo.last_for_profile(profile.id) if profile.id is not None else None
            )
            summaries.append(ProfileSummary(profile=profile, last_run=last_run))
        return summaries

    def get_profile(self, profile_id: int) -> SyncProfile:
        """Return a single profile by id, or raise :class:`ProfileNotFoundError`."""
        return self._profile_repo.get(profile_id)

    def get_profile_by_name(self, name: str) -> SyncProfile | None:
        """Return a profile by name, or ``None``."""
        return self._profile_repo.get_by_name(name)

    def add_profile(self, profile: SyncProfile) -> SyncProfile:
        """Persist a new profile and return it with an assigned id."""
        return self._profile_repo.add(profile)

    def update_profile(self, profile: SyncProfile) -> SyncProfile:
        """Persist changes to an existing profile."""
        return self._profile_repo.update(profile)

    def delete_profile(self, profile_id: int) -> None:
        """Delete a profile and its associated run records."""
        self._profile_repo.delete(profile_id)

    def list_runs(self, profile_id: int | None = None, limit: int | None = None) -> list[RunResult]:
        """Return runs for a profile or across all profiles if profile_id is None."""
        if profile_id is not None:
            return self._run_repo.list_for_profile(profile_id, limit=limit)
        return self._run_repo.list_all(limit=limit)

    def delete_run(self, run_id: int) -> bool:
        """Delete a single execution record and its log file."""
        RunLogManager().delete_log(run_id)
        return self._run_repo.delete(run_id)

    def delete_runs_for_profile(self, profile_id: int) -> int:
        """Delete all execution records and log files for a profile."""
        runs = self._run_repo.list_for_profile(profile_id)
        rids = [r.id for r in runs if r.id is not None]
        RunLogManager().delete_logs_for_runs(rids)
        return self._run_repo.delete_for_profile(profile_id)

    def clear_all_runs(self) -> int:
        """Delete all execution records and log files."""
        runs = self._run_repo.list_all()
        rids = [r.id for r in runs if r.id is not None]
        RunLogManager().delete_logs_for_runs(rids)
        return self._run_repo.clear_all()

    def get_run_log(self, run_id: int, log_dir: Path | None = None) -> str:
        """Read the execution log text for a specific run ID."""
        return RunLogManager(log_dir=log_dir).get_run_log(run_id)

    def export_run_log(self, run_id: int, target_path: Path, log_dir: Path | None = None) -> None:
        """Export the execution log of a run to a destination path."""
        RunLogManager(log_dir=log_dir).export_log(run_id, target_path)

    def close(self) -> None:
        """Close the database connection if this service opened it."""
        if self._owned_conn:
            self._conn.close()
