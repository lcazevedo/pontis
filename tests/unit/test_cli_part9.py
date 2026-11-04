# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the CLI additions in Parte 9 (export, import, import-script, watch)."""

from __future__ import annotations

from pathlib import Path

from pontis import cli
from pontis.domain.models import Endpoint, SyncProfile
from pontis.infra.database import connect
from pontis.infra.repositories import ProfileRepository


def test_cli_profile_export_and_import(tmp_path: Path, capsys: object) -> None:
    """Test CLI commands: pontis profile export and pontis profile import."""
    db_file = tmp_path / "test.db"
    conn = connect(db_file)
    repo = ProfileRepository(conn)
    repo.add(
        SyncProfile(
            name="Alpha",
            side_a=Endpoint.local("/tmp/a"),
            side_b=Endpoint.cloud("rem", "a"),
        )
    )
    repo.add(
        SyncProfile(
            name="Beta",
            side_a=Endpoint.local("/tmp/b"),
            side_b=Endpoint.cloud("rem", "b"),
        )
    )
    conn.close()

    # 1. Export single to file
    out_json = tmp_path / "exported_alpha.json"
    rc = cli.main(["--db", str(db_file), "profile", "export", "Alpha", "--output", str(out_json)])
    assert rc == 0
    assert out_json.is_file()

    # 2. Export all to stdout
    rc_all = cli.main(["--db", str(db_file), "profile", "export", "--all"])
    assert rc_all == 0

    # 3. Import from file into a fresh database
    new_db = tmp_path / "new.db"
    rc_imp = cli.main(["--db", str(new_db), "profile", "import", str(out_json)])
    assert rc_imp == 0

    new_conn = connect(new_db)
    imported = ProfileRepository(new_conn).get_by_name("Alpha")
    assert imported is not None
    assert imported.side_a.path == "/tmp/a"
    new_conn.close()


def test_cli_profile_import_script(tmp_path: Path) -> None:
    """Test CLI command: pontis profile import-script."""
    db_file = tmp_path / "test.db"
    script_file = tmp_path / "custom_sync.sh"
    script_file.write_text(
        """#!/bin/bash
LOCAL_DIR="/tmp/my_local"
REMOTE_DIR="gdrive:my_backup"

rclone bisync "$LOCAL_DIR" "$REMOTE_DIR" --exclude "*.bak" --verbose
""",
        encoding="utf-8",
    )

    rc = cli.main(
        [
            "--db",
            str(db_file),
            "profile",
            "import-script",
            str(script_file),
            "--name",
            "ImportedFromScript",
        ]
    )
    assert rc == 0

    conn = connect(db_file)
    p = ProfileRepository(conn).get_by_name("ImportedFromScript")
    assert p is not None
    assert p.side_a.path == "/tmp/my_local"
    assert p.side_b.remote == "gdrive"
    assert p.side_b.path == "my_backup"
    assert p.options.excludes == ("*.bak",)
    conn.close()


def test_cli_watch_missing_profile(tmp_path: Path) -> None:
    """Test pontis watch with a profile that does not exist."""
    db_file = tmp_path / "test.db"
    rc = cli.main(["--db", str(db_file), "watch", "NonExistentProfile"])
    assert rc == 1
