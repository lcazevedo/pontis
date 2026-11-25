# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate clean application screenshots using fictional data in temporary storage.

Usage:
    QT_QPA_PLATFORM=offscreen python scripts/generate_screenshots.py
"""

from __future__ import annotations

import os
import tempfile
from datetime import timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from pontis.domain.models import (
    ConflictPolicy,
    Endpoint,
    RunResult,
    RunStatus,
    SyncDirection,
    SyncOptions,
    SyncProfile,
    utcnow,
)
from pontis.i18n import set_language
from pontis.infra.database import connect
from pontis.infra.repositories import RunRepository
from pontis.infra.settings import AppSettings, SettingsManager
from pontis.services.profile_service import ProfileService
from pontis.services.remote_service import RemoteService
from pontis.ui.about_dialog import AboutDialog
from pontis.ui.advanced_options_dialog import AdvancedOptionsDialog
from pontis.ui.main_window import MainWindow
from pontis.ui.theme import ThemeMode, apply_theme
from pontis.ui.wizard import ProfileWizard


def _seed_demo_data(db_path: Path) -> list[SyncProfile]:
    """Populate a temporary SQLite database with fictional profiles and run history."""
    conn = connect(db_path)
    profile_service = ProfileService(conn=conn)
    run_repo = RunRepository(conn)

    now = utcnow()

    docs = profile_service.add_profile(
        SyncProfile(
            name="Documents",
            side_a=Endpoint.local("/home/user/Documents"),
            side_b=Endpoint.cloud("gdrive", "Documents"),
            options=SyncOptions(
                direction=SyncDirection.BIDIRECTIONAL,
                conflict_policy=ConflictPolicy.KEEP_BOTH,
                excludes=("*.tmp", "~$*", ".git/**"),
                check_access=True,
                transfers=4,
            ),
        )
    )
    assert docs.id is not None
    run_repo.add(
        RunResult(
            profile_id=docs.id,
            started_at=now - timedelta(minutes=18),
            finished_at=now - timedelta(minutes=17, seconds=42),
            status=RunStatus.SUCCESS,
            dry_run=False,
            files_transferred=12,
            files_deleted=0,
            errors=0,
            message="Sync completed cleanly.",
        )
    )

    projects = profile_service.add_profile(
        SyncProfile(
            name="Projects",
            side_a=Endpoint.local("/home/user/Projects"),
            side_b=Endpoint.cloud("onedrive", "Work/Projects"),
            options=SyncOptions(
                direction=SyncDirection.BIDIRECTIONAL,
                conflict_policy=ConflictPolicy.NEWER,
                excludes=("node_modules/**", ".venv/**", "__pycache__/**"),
                bandwidth_limit="5M",
            ),
        )
    )
    assert projects.id is not None
    run_repo.add(
        RunResult(
            profile_id=projects.id,
            started_at=now - timedelta(hours=2),
            finished_at=now - timedelta(hours=1, minutes=59),
            status=RunStatus.SUCCESS,
            dry_run=True,
            files_transferred=5,
            files_deleted=1,
            errors=0,
            message="Simulation completed.",
        )
    )

    photos = profile_service.add_profile(
        SyncProfile(
            name="Photos Backup",
            side_a=Endpoint.local("/home/user/Pictures"),
            side_b=Endpoint.cloud("dropbox", "Backups/Pictures"),
            options=SyncOptions(
                direction=SyncDirection.A_TO_B,
                conflict_policy=ConflictPolicy.KEEP_BOTH,
                excludes=("*.thm",),
            ),
        )
    )

    conn.close()
    return [docs, projects, photos]


def _flush_events(app: QApplication) -> None:
    """Process pending Qt layout and paint events."""
    for _ in range(5):
        app.processEvents()


def main() -> None:
    """Render screenshots into ``docs/screenshots/``."""
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "docs" / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)

    with tempfile.TemporaryDirectory(prefix="pontis_shots_") as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "pontis.db"
        rclone_conf = tmp_path / "rclone.conf"
        rclone_conf.write_text("", encoding="utf-8")
        settings_path = tmp_path / "settings.json"

        profiles = _seed_demo_data(db_path)

        # 1. Main Window (EN - Light)
        set_language("en")
        manager = SettingsManager(settings_path)
        manager.save(AppSettings(language="en", theme="light", check_updates_on_startup=False))

        win = MainWindow(
            db_path=db_path,
            rclone_binary="rclone",
            rclone_config=rclone_conf,
            settings_manager=manager,
            check_updates_on_startup=False,
        )
        win.set_theme(ThemeMode.LIGHT)
        win.resize(980, 520)
        win.show()
        win._table.selectRow(0)
        _flush_events(app)
        win.grab().save(str(out_dir / "main_window_light.png"))

        # 2. Main Window (EN - Dark)
        win.set_theme(ThemeMode.DARK)
        _flush_events(app)
        win.grab().save(str(out_dir / "main_window_dark.png"))

        # 3. Main Window (PT-BR - Light)
        set_language("pt_BR")
        win.set_theme(ThemeMode.LIGHT)
        win._table.selectRow(0)
        _flush_events(app)
        win.grab().save(str(out_dir / "main_window_pt_br.png"))

        # 4. Wizard (EN - Light)
        set_language("en")
        remote_svc = RemoteService(binary="rclone", config_path=rclone_conf)
        wizard = ProfileWizard(
            service=win._service,
            remote_service=remote_svc,
            profile=profiles[0],
        )
        apply_theme(wizard, ThemeMode.LIGHT)
        wizard.resize(700, 500)
        wizard.show()
        _flush_events(app)
        wizard.grab().save(str(out_dir / "wizard.png"))
        wizard.close()

        # 5. Advanced Options Dialog (EN - Light)
        adv = AdvancedOptionsDialog(
            profile=profiles[0],
            rclone_binary="rclone",
            rclone_config=rclone_conf,
        )
        apply_theme(adv, ThemeMode.LIGHT)
        adv.resize(760, 580)
        adv.show()
        _flush_events(app)
        adv.grab().save(str(out_dir / "advanced_options.png"))
        adv.close()

        # 6. About Dialog (EN - Light)
        about = AboutDialog(rclone_binary="rclone")
        apply_theme(about, ThemeMode.LIGHT)
        about.show()
        _flush_events(app)
        about.grab().save(str(out_dir / "about_dialog.png"))
        about.close()

        win.close()

    for png in sorted(out_dir.glob("*.png")):
        print(f"Generated {png.relative_to(repo_root)} ({png.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
