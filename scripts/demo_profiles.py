# SPDX-License-Identifier: GPL-3.0-or-later
"""Create, edit and delete a profile in a throwaway database (manual test for Part 1).

Usage: python scripts/demo_profiles.py [create|edit|delete|list] [DB_PATH]
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from pontis.domain import Endpoint, SyncOptions, SyncProfile
from pontis.infra import database
from pontis.infra.repositories import ProfileRepository


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    db = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.gettempdir()) / "pontis_demo.db"
    repo = ProfileRepository(database.connect(db))
    if action == "create":
        if repo.get_by_name("Demo"):
            print("O perfil 'Demo' já existe; use 'delete' antes de criar de novo.")
            return
        repo.add(
            SyncProfile(
                name="Demo",
                side_a=Endpoint.local("/tmp/pontis_a"),
                side_b=Endpoint.cloud("gdrive", "PontisTeste"),
                options=SyncOptions(excludes=("*.tmp",)),
            )
        )
    elif action == "edit":
        profile = repo.get_by_name("Demo")
        if profile:
            profile.name = "Demo editado"
            repo.update(profile)
    elif action == "delete":
        for profile in repo.list():
            if profile.id is not None:
                repo.delete(profile.id)
    print(f"Banco: {db}")
    for profile in repo.list():
        print(
            f"- [{profile.id}] {profile.name}: {profile.side_a.to_rclone()} <-> "
            f"{profile.side_b.to_rclone()}"
        )


if __name__ == "__main__":
    main()
