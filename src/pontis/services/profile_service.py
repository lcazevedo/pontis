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

    def close(self) -> None:
        """Close the database connection if this service opened it."""
        if self._owned_conn:
            self._conn.close()
