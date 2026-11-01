# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ProfileWizard, EndpointPickerWidget, and CloudFolderBrowserDialog."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QWizard
from pytestqt.qtbot import QtBot

from pontis.domain.models import (
    ConflictPolicy,
    Endpoint,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.infra.database import connect
from pontis.infra.keyring_store import KeyringStore
from pontis.infra.rclone import locate_rclone
from pontis.services.profile_service import ProfileService
from pontis.services.remote_service import RemoteService
from pontis.ui.main_window import MainWindow
from pontis.ui.widgets.cloud_browser_dialog import CloudFolderBrowserDialog
from pontis.ui.wizard import ProfileWizard


class FakeKeyring(KeyringStore):
    """In-memory keyring for testing."""

    def __init__(self) -> None:
        super().__init__("pontis-test")
        self._store: dict[str, str] = {}

    def get_password(self, username: str = "rclone_config_pass") -> str | None:
        return self._store.get(username)

    def set_password(self, password: str, username: str = "rclone_config_pass") -> None:
        self._store[username] = password

    def delete_password(self, username: str = "rclone_config_pass") -> bool:
        return self._store.pop(username, None) is not None

    def has_password(self, username: str = "rclone_config_pass") -> bool:
        return username in self._store


@pytest.fixture
def test_env(tmp_path: Path) -> tuple[ProfileService, RemoteService]:
    db_path = tmp_path / "wizard_test.db"
    conn = connect(db_path)
    profile_service = ProfileService(conn=conn)

    config_path = tmp_path / "rclone.conf"
    # Create an initial rclone.conf with a test Google Drive remote
    config_path.write_text(
        "[gdrive]\ntype = drive\nscope = drive\n\n[backup_s3]\ntype = s3\n",
        encoding="utf-8",
    )
    rclone_info = locate_rclone()
    remote_service = RemoteService(
        binary=rclone_info.path, config_path=config_path, keyring_store=FakeKeyring()
    )

    return profile_service, remote_service


def test_wizard_create_profile_flow(
    qtbot: QtBot, test_env: tuple[ProfileService, RemoteService], tmp_path: Path
) -> None:
    profile_svc, remote_svc = test_env
    local_dir = tmp_path / "local_docs"
    local_dir.mkdir()

    wizard = ProfileWizard(service=profile_svc, remote_service=remote_svc)
    qtbot.addWidget(wizard)
    wizard.show()

    # Page 1: Name validation
    name_page = wizard.page_name
    assert not name_page.isComplete()

    # Set valid name
    name_page._edit_name.setText("WorkSync")
    assert name_page.isComplete()
    wizard.next()

    # Page 2: Side A (Local)
    side_a_page = wizard.page_side_a
    assert not side_a_page.isComplete()
    side_a_page.picker._edit_local_path.setText(str(local_dir))
    assert side_a_page.isComplete()
    wizard.next()

    # Page 3: Side B (Cloud: gdrive:WorkBackup)
    side_b_page = wizard.page_side_b
    side_b_page.picker._rb_remote.setChecked(True)
    idx = side_b_page.picker._remote_combo.findData("gdrive")
    assert idx >= 0
    side_b_page.picker._remote_combo.setCurrentIndex(idx)
    side_b_page.picker._edit_remote_path.setText("WorkBackup")
    assert side_b_page.isComplete()
    wizard.next()

    # Page 4: Direction
    direction_page = wizard.page_direction
    assert direction_page.sync_direction() == SyncDirection.BIDIRECTIONAL
    direction_page._rb_a_to_b.setChecked(True)
    assert direction_page.sync_direction() == SyncDirection.A_TO_B
    wizard.next()

    # Page 5: Conflict policy
    conflict_page = wizard.page_conflict
    assert conflict_page.conflict_policy() == ConflictPolicy.KEEP_BOTH
    conflict_page._rb_newer.setChecked(True)
    assert conflict_page.conflict_policy() == ConflictPolicy.NEWER
    wizard.next()

    # Page 6: Summary
    summary_page = wizard.page_summary
    assert summary_page._lbl_name.text() == "WorkSync"
    assert summary_page._lbl_side_a.text() == str(local_dir)
    assert "gdrive:WorkBackup" in summary_page._lbl_side_b.text()

    # Complete the wizard
    wizard.accept()

    # Verify profile created in SQLite
    saved = wizard.saved_profile
    assert saved is not None
    assert saved.id is not None
    assert saved.name == "WorkSync"
    assert saved.side_a.path == str(local_dir)
    assert saved.side_b.remote == "gdrive"
    assert saved.side_b.path == "WorkBackup"
    assert saved.options.direction == SyncDirection.A_TO_B
    assert saved.options.conflict_policy == ConflictPolicy.NEWER


def test_wizard_duplicate_name_and_same_endpoints_validation(
    qtbot: QtBot, test_env: tuple[ProfileService, RemoteService], tmp_path: Path
) -> None:
    profile_svc, remote_svc = test_env

    # Pre-existing profile
    profile_svc.add_profile(
        SyncProfile(
            name="ExistingProfile",
            side_a=Endpoint.local("/tmp/a"),
            side_b=Endpoint.cloud("gdrive", "b"),
        )
    )

    wizard = ProfileWizard(service=profile_svc, remote_service=remote_svc)
    qtbot.addWidget(wizard)
    wizard.show()

    # Duplicate name should be rejected
    wizard.page_name._edit_name.setText("ExistingProfile")
    assert not wizard.page_name.isComplete()
    assert wizard.page_name._lbl_error.isVisible()

    wizard.page_name._edit_name.setText("UniqueName")
    assert wizard.page_name.isComplete()
    wizard.next()

    # Side A: local /tmp/same
    wizard.page_side_a.picker._edit_local_path.setText("/tmp/same")
    assert wizard.page_side_a.isComplete()
    wizard.next()

    # Side B: local /tmp/same (identical endpoint should be rejected)
    wizard.page_side_b.picker._edit_local_path.setText("/tmp/same")
    assert not wizard.page_side_b.isComplete()
    assert wizard.page_side_b._lbl_error.isVisible()

    # Changing Side B makes it valid
    wizard.page_side_b.picker._edit_local_path.setText("/tmp/other")
    assert wizard.page_side_b.isComplete()


def test_wizard_edit_profile_flow(
    qtbot: QtBot, test_env: tuple[ProfileService, RemoteService]
) -> None:
    profile_svc, remote_svc = test_env

    initial_profile = profile_svc.add_profile(
        SyncProfile(
            name="OriginalProfile",
            side_a=Endpoint.local("/home/user/orig_local"),
            side_b=Endpoint.cloud("gdrive", "orig_cloud"),
            options=SyncOptions(
                direction=SyncDirection.BIDIRECTIONAL,
                conflict_policy=ConflictPolicy.KEEP_BOTH,
            ),
        )
    )
    assert initial_profile.id is not None

    wizard = ProfileWizard(service=profile_svc, remote_service=remote_svc, profile=initial_profile)
    qtbot.addWidget(wizard)
    wizard.show()

    assert "OriginalProfile" in wizard.windowTitle()
    assert wizard.page_name.profile_name() == "OriginalProfile"
    assert wizard.page_name.isComplete()

    # Rename
    wizard.page_name._edit_name.setText("UpdatedProfile")
    wizard.next()

    # Update Side A path
    wizard.page_side_a.picker._edit_local_path.setText("/home/user/updated_local")
    wizard.next()

    # Side B should keep cloud and remote path
    assert wizard.page_side_b.picker._rb_remote.isChecked()
    assert wizard.page_side_b.picker._edit_remote_path.text() == "orig_cloud"
    wizard.page_side_b.picker._edit_remote_path.setText("updated_cloud")
    wizard.next()

    # Change direction to B_TO_A
    wizard.page_direction._rb_b_to_a.setChecked(True)
    wizard.next()

    # Change conflict policy to larger
    wizard.page_conflict._rb_larger.setChecked(True)
    wizard.next()

    # Accept
    wizard.accept()

    updated = wizard.saved_profile
    assert updated is not None
    assert updated.id == initial_profile.id
    assert updated.name == "UpdatedProfile"
    assert updated.side_a.path == "/home/user/updated_local"
    assert updated.side_b.path == "updated_cloud"
    assert updated.options.direction == SyncDirection.B_TO_A
    assert updated.options.conflict_policy == ConflictPolicy.LARGER

    # Verify persisted in SQLite
    reloaded = profile_svc.get_profile(initial_profile.id)
    assert reloaded.name == "UpdatedProfile"
    assert reloaded.side_b.path == "updated_cloud"


def test_cloud_folder_browser_dialog(
    qtbot: QtBot, test_env: tuple[ProfileService, RemoteService]
) -> None:
    _, remote_svc = test_env

    with patch.object(
        remote_svc,
        "list_directories",
        return_value=["Folder1", "Folder2", "Folder3"],
    ):
        dialog = CloudFolderBrowserDialog(
            remote_service=remote_svc, initial_remote="gdrive", initial_path=""
        )
        qtbot.addWidget(dialog)
        dialog.show()

        assert dialog._folder_list.count() == 3
        assert dialog._folder_list.item(0).text() == "Folder1"

        # Double click Folder2
        item = dialog._folder_list.item(1)
        dialog._on_item_double_clicked(item)
        assert dialog.selected_path() == "Folder2"

        # Up button goes back to root
        dialog._on_up_clicked()
        assert dialog.selected_path() == ""


def test_main_window_integration_with_wizard(
    qtbot: QtBot, test_env: tuple[ProfileService, RemoteService], tmp_path: Path
) -> None:
    profile_svc, remote_svc = test_env

    window = MainWindow(service=profile_svc, remote_service=remote_svc)
    qtbot.addWidget(window)
    window.show()

    # 1. Initially empty state
    assert window._stack.currentIndex() == 1
    assert not window._action_edit.isEnabled()

    # 2. Trigger New Profile
    with (
        patch.object(ProfileWizard, "exec", return_value=QWizard.DialogCode.Accepted),
        patch.object(
            ProfileWizard,
            "saved_profile",
            SyncProfile(
                name="GUICreated",
                side_a=Endpoint.local("/tmp/a"),
                side_b=Endpoint.cloud("gdrive", "b"),
                id=1,
            ),
        ),
    ):
        window._on_new_profile()

    # 3. Add real profile and reload to verify Edit action
    profile_svc.add_profile(
        SyncProfile(
            name="RealGUIProfile",
            side_a=Endpoint.local("/tmp/real_a"),
            side_b=Endpoint.cloud("gdrive", "real_b"),
        )
    )
    window.load_profiles()
    assert window._stack.currentIndex() == 0
    assert window._table.rowCount() == 1

    # Select row and check Edit action enabled
    window._table.selectRow(0)
    assert window._action_edit.isEnabled()
    assert window._action_delete.isEnabled()

    # Double click cell triggers edit
    with patch.object(window, "_on_edit_profile") as mock_edit:
        window._table.cellDoubleClicked.emit(0, 0)
        mock_edit.assert_called_once()
