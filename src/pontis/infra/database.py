# SPDX-License-Identifier: GPL-3.0-or-later
"""SQLite connection handling and versioned migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pontis.infra.paths import default_db_path

# Each entry is one migration; its schema version is its 1-based position.
# Never edit an existing entry: append a new one instead.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE profiles (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL UNIQUE,
        side_a      TEXT NOT NULL,
        side_b      TEXT NOT NULL,
        options     TEXT NOT NULL,
        schedule    TEXT,            -- reserved for the future, NULL = manual
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    );
    CREATE TABLE runs (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id         INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        started_at         TEXT NOT NULL,
        finished_at        TEXT,
        status             TEXT NOT NULL,
        dry_run            INTEGER NOT NULL DEFAULT 0,
        files_transferred  INTEGER NOT NULL DEFAULT 0,
        files_deleted      INTEGER NOT NULL DEFAULT 0,
        errors             INTEGER NOT NULL DEFAULT 0,
        message            TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX idx_runs_profile ON runs(profile_id, started_at DESC);
    """,
)

LATEST_VERSION = len(MIGRATIONS)


def schema_version(conn: sqlite3.Connection) -> int:
    """Return the schema version stored in the database."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def migrate(conn: sqlite3.Connection) -> None:
    """Apply pending migrations, each in its own transaction."""
    current = schema_version(conn)
    if current > LATEST_VERSION:
        raise RuntimeError(
            f"Database schema version {current} is newer than supported ({LATEST_VERSION})."
        )
    for version in range(current + 1, LATEST_VERSION + 1):
        try:
            conn.execute("BEGIN")
            for statement in _split(MIGRATIONS[version - 1]):
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {version}")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise


def _split(script: str) -> list[str]:
    """Split a migration script into statements (no semicolons inside literals)."""
    return [s.strip() for s in script.split(";") if s.strip()]


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open the database (default: the app data dir) and migrate it to the latest version.

    Use ``":memory:"`` for an in-memory database.
    """
    target = default_db_path() if db_path is None else db_path
    # isolation_level=None: autocommit, transactions are managed explicitly.
    conn = sqlite3.connect(target, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn
