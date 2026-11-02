# SPDX-License-Identifier: GPL-3.0-or-later
"""SQLite repositories for profiles and run history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from pontis.domain.models import (
    Endpoint,
    RunResult,
    RunStatus,
    Schedule,
    SyncOptions,
    SyncProfile,
    utcnow,
)


class DuplicateProfileError(Exception):
    """Raised when a profile name is already in use."""


class ProfileNotFoundError(LookupError):
    """Raised when a profile id does not exist."""


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class ProfileRepository:
    """CRUD for :class:`SyncProfile`."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, profile: SyncProfile) -> SyncProfile:
        """Insert a new profile and set its ``id``."""
        try:
            cur = self._conn.execute(
                "INSERT INTO profiles (name, side_a, side_b, options, schedule,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    profile.name,
                    json.dumps(profile.side_a.to_dict()),
                    json.dumps(profile.side_b.to_dict()),
                    json.dumps(profile.options.to_dict()),
                    json.dumps(profile.schedule.to_dict()),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateProfileError(profile.name) from exc
        profile.id = cur.lastrowid
        return profile

    def get(self, profile_id: int) -> SyncProfile:
        """Return a profile by id."""
        row = self._conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            raise ProfileNotFoundError(profile_id)
        return self._from_row(row)

    def get_by_name(self, name: str) -> SyncProfile | None:
        """Return a profile by name, or ``None``."""
        row = self._conn.execute("SELECT * FROM profiles WHERE name = ?", (name,)).fetchone()
        return None if row is None else self._from_row(row)

    def list(self) -> list[SyncProfile]:
        """Return all profiles ordered by name."""
        rows = self._conn.execute("SELECT * FROM profiles ORDER BY name COLLATE NOCASE").fetchall()
        return [self._from_row(r) for r in rows]

    def update(self, profile: SyncProfile) -> SyncProfile:
        """Persist changes to an existing profile and refresh ``updated_at``."""
        if profile.id is None:
            raise ValueError("Cannot update a profile without an id.")
        profile.updated_at = utcnow()
        try:
            cur = self._conn.execute(
                "UPDATE profiles SET name = ?, side_a = ?, side_b = ?, options = ?,"
                " schedule = ?, updated_at = ? WHERE id = ?",
                (
                    profile.name,
                    json.dumps(profile.side_a.to_dict()),
                    json.dumps(profile.side_b.to_dict()),
                    json.dumps(profile.options.to_dict()),
                    json.dumps(profile.schedule.to_dict()),
                    profile.updated_at.isoformat(),
                    profile.id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateProfileError(profile.name) from exc
        if cur.rowcount == 0:
            raise ProfileNotFoundError(profile.id)
        return profile

    def delete(self, profile_id: int) -> None:
        """Delete a profile (its run history is removed by cascade)."""
        cur = self._conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        if cur.rowcount == 0:
            raise ProfileNotFoundError(profile_id)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> SyncProfile:
        schedule_raw = row["schedule"]
        return SyncProfile(
            id=row["id"],
            name=row["name"],
            side_a=Endpoint.from_dict(json.loads(row["side_a"])),
            side_b=Endpoint.from_dict(json.loads(row["side_b"])),
            options=SyncOptions.from_dict(json.loads(row["options"])),
            schedule=Schedule.from_dict(json.loads(schedule_raw)) if schedule_raw else Schedule(),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )


class RunRepository:
    """Run history storage for :class:`RunResult`."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, result: RunResult) -> RunResult:
        """Insert a run record and set its ``id``."""
        cur = self._conn.execute(
            "INSERT INTO runs (profile_id, started_at, finished_at, status, dry_run,"
            " files_transferred, files_deleted, errors, message)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self._values(result),
        )
        result.id = cur.lastrowid
        return result

    def update(self, result: RunResult) -> RunResult:
        """Persist changes to an existing run (e.g. when it finishes)."""
        if result.id is None:
            raise ValueError("Cannot update a run without an id.")
        self._conn.execute(
            "UPDATE runs SET profile_id = ?, started_at = ?, finished_at = ?, status = ?,"
            " dry_run = ?, files_transferred = ?, files_deleted = ?, errors = ?, message = ?"
            " WHERE id = ?",
            (*self._values(result), result.id),
        )
        return result

    def get(self, run_id: int) -> RunResult | None:
        """Return a run by id, or ``None``."""
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return None if row is None else self._from_row(row)

    def list_for_profile(self, profile_id: int, limit: int | None = None) -> list[RunResult]:
        """Return runs of a profile, newest first."""
        sql = "SELECT * FROM runs WHERE profile_id = ? ORDER BY started_at DESC, id DESC"
        params: tuple[int, ...] = (profile_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (profile_id, limit)
        return [self._from_row(r) for r in self._conn.execute(sql, params).fetchall()]

    def list_all(self, limit: int | None = None) -> list[RunResult]:
        """Return all runs across profiles, newest first."""
        sql = "SELECT * FROM runs ORDER BY started_at DESC, id DESC"
        params: tuple[int, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        return [self._from_row(r) for r in self._conn.execute(sql, params).fetchall()]

    def last_for_profile(self, profile_id: int) -> RunResult | None:
        """Return the most recent run of a profile, or ``None``."""
        runs = self.list_for_profile(profile_id, limit=1)
        return runs[0] if runs else None

    def delete(self, run_id: int) -> bool:
        """Delete a single run record by ID."""
        cur = self._conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        return cur.rowcount > 0

    def delete_for_profile(self, profile_id: int) -> int:
        """Delete all runs of a profile; return how many were removed."""
        return self._conn.execute("DELETE FROM runs WHERE profile_id = ?", (profile_id,)).rowcount

    def clear_all(self) -> int:
        """Delete all runs from the database; return how many were removed."""
        return self._conn.execute("DELETE FROM runs").rowcount

    @staticmethod
    def _values(r: RunResult) -> tuple[object, ...]:
        return (
            r.profile_id,
            r.started_at.isoformat(),
            r.finished_at.isoformat() if r.finished_at else None,
            r.status.value,
            int(r.dry_run),
            r.files_transferred,
            r.files_deleted,
            r.errors,
            r.message,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> RunResult:
        return RunResult(
            id=row["id"],
            profile_id=row["profile_id"],
            started_at=_dt(row["started_at"]),
            finished_at=_dt(row["finished_at"]) if row["finished_at"] else None,
            status=RunStatus(row["status"]),
            dry_run=bool(row["dry_run"]),
            files_transferred=row["files_transferred"],
            files_deleted=row["files_deleted"],
            errors=row["errors"],
            message=row["message"],
        )
