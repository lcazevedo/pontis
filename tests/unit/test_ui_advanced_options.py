# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit and UI tests for the AdvancedOptionsDialog and related workflows."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from pontis.domain.models import (
    ConflictPolicy,
    Endpoint,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.infra.database import connect
from pontis.services.profile_service import ProfileService
from pontis.services.remote_service import RemoteService
from pontis.ui.advanced_options_dialog import AdvancedOptionsDialog
from pontis.ui.main_window import MainWindow
from pontis.ui.wizard import ProfileWizard


@pytest.fixture
def db_conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(tmp_path / "test.db")
    yield conn
    conn.close()


@pytest.fixture
def profile_service(db_conn: sqlite3.Connection) -> ProfileService:
    return ProfileService(conn=db_conn)


@pytest.fixture
def sample_profile() -> SyncProfile:
    return SyncProfile(
        name="SENAI",
        side_a=Endpoint.local("/home/lcazevedo/Documents/SENAI"),
        side_b=Endpoint.cloud("gdrive", "SENAI"),
        options=SyncOptions(
            direction=SyncDirection.BIDIRECTIONAL,
            conflict_policy=ConflictPolicy.KEEP_BOTH,
            max_delete_percent=50,
            check_access=False,
        ),
        id=1,
    )


def test_advanced_dialog_init(qtbot: QtBot, sample_profile: SyncProfile, tmp_path: Path) -> None:
    dialog = AdvancedOptionsDialog(
        profile=sample_profile,
        rclone_binary="rclone",
        rclone_config=tmp_path / "rclone.conf",
    )
    qtbot.addWidget(dialog)

    title = dialog.windowTitle()
    assert title.startswith("Opções Avançadas") or title.startswith("Advanced Options")
    assert dialog._spin_max_delete.value() == 50
    assert dialog._combo_conflict.currentData() == ConflictPolicy.KEEP_BOTH
    assert not dialog._chk_check_access.isChecked()
    assert dialog._btn_save.isEnabled()


def test_advanced_dialog_reproduce_sync_sh_excludes(
    qtbot: QtBot, sample_profile: SyncProfile, tmp_path: Path
) -> None:
    """Reproduces the exact parameters from user's sync.sh:
    - --conflict-resolve newer
    - --exclude 'sync.sh'
    - --exclude '.opencode/**'
    - --exclude '**/node_modules/**'
    and verifies the live command preview reflects all of them correctly.
    """
    dialog = AdvancedOptionsDialog(
        profile=sample_profile,
        rclone_binary="rclone",
        rclone_config=tmp_path / "rclone.conf",
    )
    qtbot.addWidget(dialog)

    # 1. Select ConflictPolicy.NEWER
    idx = dialog._combo_conflict.findData(ConflictPolicy.NEWER)
    assert idx >= 0
    dialog._combo_conflict.setCurrentIndex(idx)

    # 2. Add the three excludes from sync.sh
    excludes_to_add = ["sync.sh", ".opencode/**", "**/node_modules/**"]
    for pattern in excludes_to_add:
        dialog._edit_exclude.setText(pattern)
        dialog._btn_add_exclude.click()

    assert dialog._list_excludes.count() == 3

    # 3. Verify preview command line
    preview = dialog._preview_text.toPlainText()
    assert "rclone" in preview
    assert "bisync" in preview
    assert "/home/lcazevedo/Documents/SENAI" in preview
    assert "gdrive:SENAI" in preview
    assert "--conflict-resolve newer" in preview
    assert "--exclude sync.sh" in preview
    assert ".opencode/**" in preview
    assert "node_modules" in preview
    assert "--max-delete 50" in preview

    # 4. Check dry-run toggle
    dialog._chk_dry_run.setChecked(True)
    assert "--dry-run" in dialog._preview_text.toPlainText()
    dialog._chk_dry_run.setChecked(False)
    assert "--dry-run" not in dialog._preview_text.toPlainText()

    # 5. Check first-run resync toggle
    dialog._chk_resync.setChecked(True)
    resync_cmd = dialog._preview_text.toPlainText()
    assert "--resync" in resync_cmd
    assert "--resync-mode newer" in resync_cmd
    assert "--max-delete" not in resync_cmd


def test_filters_add_remove_clear(
    qtbot: QtBot, sample_profile: SyncProfile, tmp_path: Path
) -> None:
    dialog = AdvancedOptionsDialog(profile=sample_profile, rclone_binary="rclone")
    qtbot.addWidget(dialog)

    # Adding empty or duplicates
    dialog._edit_exclude.setText("   ")
    dialog._btn_add_exclude.click()
    assert dialog._list_excludes.count() == 0

    dialog._edit_exclude.setText("*.bak")
    dialog._btn_add_exclude.click()
    assert dialog._list_excludes.count() == 1

    dialog._edit_exclude.setText("*.bak")
    dialog._btn_add_exclude.click()
    assert dialog._list_excludes.count() == 1  # No duplicates

    # Includes
    dialog._edit_include.setText("*.pdf")
    dialog._btn_add_include.click()
    assert dialog._list_includes.count() == 1
    assert "--include" in dialog._preview_text.toPlainText()

    # Remove selected
    dialog._list_excludes.setCurrentRow(0)
    dialog._btn_remove_exclude.click()
    assert dialog._list_excludes.count() == 0

    # Clear all
    dialog._edit_include.setText("*.docx")
    dialog._btn_add_include.click()
    assert dialog._list_includes.count() == 2
    dialog._btn_clear_includes.click()
    assert dialog._list_includes.count() == 0


def test_validation_forbidden_extra_flags(qtbot: QtBot, sample_profile: SyncProfile) -> None:
    dialog = AdvancedOptionsDialog(profile=sample_profile, rclone_binary="rclone")
    qtbot.addWidget(dialog)

    # Valid custom flag
    dialog._edit_flags.setPlainText("--fast-list")
    assert dialog._btn_save.isEnabled()
    assert not dialog._lbl_flags_error.isVisible()
    assert "--fast-list" in dialog._preview_text.toPlainText()

    # Forbidden flag managed by app
    dialog._edit_flags.setPlainText("--fast-list\n--resync")
    assert not dialog._btn_save.isEnabled()
    assert not dialog._lbl_flags_error.isHidden()
    assert "resync" in dialog._lbl_flags_error.text().lower()

    # Invalid syntax (doesn't start with hyphen)
    dialog._edit_flags.setPlainText("invalid_flag_without_dash")
    assert not dialog._btn_save.isEnabled()
    assert not dialog._lbl_flags_error.isHidden()

    # Correct it back
    dialog._edit_flags.setPlainText("--drive-skip-gdocs")
    assert dialog._btn_save.isEnabled()
    assert dialog._lbl_flags_error.isHidden()


def test_bandwidth_and_transfers(qtbot: QtBot, sample_profile: SyncProfile) -> None:
    dialog = AdvancedOptionsDialog(profile=sample_profile, rclone_binary="rclone")
    qtbot.addWidget(dialog)

    # Bandwidth limit
    dialog._edit_bwlimit.setText("10M")
    assert "--bwlimit 10M" in dialog._preview_text.toPlainText()

    # Invalid bandwidth syntax
    dialog._edit_bwlimit.setText("10M; rm -rf /")
    assert not dialog._btn_save.isEnabled()
    assert not dialog._lbl_bw_error.isHidden()

    dialog._edit_bwlimit.setText("10M:off")
    assert dialog._btn_save.isEnabled()
    assert dialog._lbl_bw_error.isHidden()

    # Transfers
    assert not dialog._chk_enable_transfers.isChecked()
    assert "--transfers" not in dialog._preview_text.toPlainText()

    dialog._chk_enable_transfers.setChecked(True)
    dialog._spin_transfers.setValue(8)
    assert "--transfers 8" in dialog._preview_text.toPlainText()


def test_copy_button_and_reset(
    qtbot: QtBot, sample_profile: SyncProfile, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = AdvancedOptionsDialog(profile=sample_profile, rclone_binary="rclone")
    qtbot.addWidget(dialog)

    # Copy button
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.clear()
        dialog._btn_copy.click()
        assert "rclone" in clipboard.text()

    # Modify values then reset to defaults
    dialog._slider_max_delete.setValue(80)
    dialog._chk_check_access.setChecked(True)

    # Confirm dialog answering Yes
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    dialog._btn_reset.click()

    assert dialog._spin_max_delete.value() == 50
    assert not dialog._chk_check_access.isChecked()


def test_save_and_cancel_options(qtbot: QtBot, sample_profile: SyncProfile) -> None:
    dialog = AdvancedOptionsDialog(profile=sample_profile, rclone_binary="rclone")
    qtbot.addWidget(dialog)

    dialog._edit_exclude.setText("*.tmp")
    dialog._btn_add_exclude.click()
    dialog._chk_check_access.setChecked(True)
    dialog._slider_max_delete.setValue(25)

    # Click Save
    dialog._btn_save.click()
    assert dialog.result() == 1  # Accepted

    opts = dialog.get_options()
    assert "*.tmp" in opts.excludes
    assert opts.check_access is True
    assert opts.max_delete_percent == 25
    assert sample_profile.options.max_delete_percent == 25


def test_main_window_advanced_action(
    qtbot: QtBot,
    profile_service: ProfileService,
    sample_profile: SyncProfile,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved = profile_service.add_profile(sample_profile)
    assert saved.id is not None

    remote_mock = RemoteService(binary="rclone", config_path=tmp_path / "rclone.conf")
    window = MainWindow(service=profile_service, remote_service=remote_mock)
    qtbot.addWidget(window)

    # Before selection, advanced action is disabled
    window._table.clearSelection()
    window._on_selection_changed()
    assert not window._action_advanced.isEnabled()

    # Select profile row
    window._table.selectRow(0)
    assert window._action_advanced.isEnabled()

    # Mock dialog execution to modify max_delete
    def mock_exec(dialog_self: AdvancedOptionsDialog) -> int:
        dialog_self._slider_max_delete.setValue(15)
        dialog_self._on_save()
        return 1

    monkeypatch.setattr(AdvancedOptionsDialog, "exec", mock_exec)

    window._action_advanced.trigger()

    # Check updated profile in database
    reloaded = profile_service.get_profile(saved.id)
    assert reloaded.options.max_delete_percent == 15


def test_wizard_advanced_options_integration(
    qtbot: QtBot,
    profile_service: ProfileService,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote_mock = RemoteService(binary="rclone", config_path=tmp_path / "rclone.conf")
    wizard = ProfileWizard(service=profile_service, remote_service=remote_mock)
    qtbot.addWidget(wizard)

    # Set up fields
    wizard.page_name._edit_name.setText("SENAI_Job")
    wizard.page_side_a.picker.set_endpoint(Endpoint.local("/home/lcazevedo/Documents/SENAI"))
    wizard.page_side_b.picker.set_endpoint(Endpoint.local("/tmp/backup"))

    # Mock advanced options dialog to set excludes
    def mock_exec(dialog_self: AdvancedOptionsDialog) -> int:
        dialog_self._edit_exclude.setText("sync.sh")
        dialog_self._btn_add_exclude.click()
        dialog_self._on_save()
        return 1

    monkeypatch.setattr(AdvancedOptionsDialog, "exec", mock_exec)

    # Click advanced options button from summary page
    wizard.page_summary._on_open_advanced()

    assert "sync.sh" in wizard.custom_options.excludes

    # Accept wizard
    wizard.accept()

    saved = profile_service.get_profile_by_name("SENAI_Job")
    assert saved is not None
    assert "sync.sh" in saved.options.excludes
