# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for RemoteService, KeyringStore, and remote CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pontis.cli import main
from pontis.domain.models import RemoteInfo, RemoteTestResult
from pontis.infra.keyring_store import KeyringStore
from pontis.infra.rclone import locate_rclone
from pontis.services.remote_service import (
    RemoteAlreadyExistsError,
    RemoteInvalidNameError,
    RemoteNotFoundError,
    RemoteService,
)


@pytest.fixture
def rclone_path() -> Path:
    info = locate_rclone()
    return info.path


class FakeKeyringStore(KeyringStore):
    """In-memory keyring implementation for tests."""

    def __init__(self) -> None:
        super().__init__("pontis-test")
        self._store: dict[str, str] = {}

    def get_password(self, username: str = "rclone_config_pass") -> str | None:
        return self._store.get(username)

    def set_password(self, password: str, username: str = "rclone_config_pass") -> None:
        self._store[username] = password

    def delete_password(self, username: str = "rclone_config_pass") -> bool:
        if username in self._store:
            del self._store[username]
            return True
        return False

    def has_password(self, username: str = "rclone_config_pass") -> bool:
        return username in self._store


def test_remote_info_and_result_models() -> None:
    info = RemoteInfo(name="mydrive", type="drive", parameters={"client_id": "xyz"})
    d = info.to_dict()
    assert d["name"] == "mydrive"
    assert d["type"] == "drive"
    assert d["parameters"]["client_id"] == "xyz"

    restored = RemoteInfo.from_dict(d)
    assert restored.name == info.name
    assert restored.type == info.type
    assert restored.parameters == info.parameters

    res = RemoteTestResult(remote="mydrive", success=True, storage_info={"total": 1000})
    assert res.success is True
    assert res.storage_info == {"total": 1000}


def test_keyring_store_mocked() -> None:
    with (
        patch("keyring.get_password") as mock_get,
        patch("keyring.set_password") as mock_set,
        patch("keyring.delete_password") as mock_del,
    ):
        mock_get.return_value = "secret123"
        store = KeyringStore("test-service")

        assert store.get_password() == "secret123"
        mock_get.assert_called_once_with("test-service", "rclone_config_pass")
        assert store.has_password() is True

        store.set_password("newsecret")
        mock_set.assert_called_once_with("test-service", "rclone_config_pass", "newsecret")

        assert store.delete_password() is True
        mock_del.assert_called_once_with("test-service", "rclone_config_pass")


def test_remote_service_empty_config(tmp_path: Path, rclone_path: Path) -> None:
    config_path = tmp_path / "nonexistent_rclone.conf"
    service = RemoteService(rclone_path, config_path, FakeKeyringStore())

    assert service.list_remotes() == []
    assert service.get_remote("anything") is None


def test_remote_service_invalid_name(tmp_path: Path, rclone_path: Path) -> None:
    config_path = tmp_path / "rclone.conf"
    service = RemoteService(rclone_path, config_path, FakeKeyringStore())

    with pytest.raises(RemoteInvalidNameError):
        service.add_remote("bad:name", "alias")

    with pytest.raises(RemoteInvalidNameError):
        service.add_remote("", "alias")


def test_remote_service_add_get_delete_lifecycle(tmp_path: Path, rclone_path: Path) -> None:
    config_path = tmp_path / "rclone.conf"
    service = RemoteService(rclone_path, config_path, FakeKeyringStore())

    target_dir = tmp_path / "target"
    target_dir.mkdir()

    # 1. Add remote
    created = service.add_remote(
        "testlocal",
        "alias",
        {"remote": str(target_dir)},
        interactive=False,
    )
    assert created.name == "testlocal"
    assert created.type == "alias"
    assert config_path.is_file()

    # Check permission (0600)
    assert (config_path.stat().st_mode & 0o777) == 0o600

    # 2. Get remote
    found = service.get_remote("testlocal")
    assert found is not None
    assert found.name == "testlocal"
    assert found.type == "alias"
    assert found.parameters.get("remote") == str(target_dir)

    # 3. List remotes
    remotes = service.list_remotes()
    assert len(remotes) == 1
    assert remotes[0].name == "testlocal"

    # 4. Duplicate rejection
    with pytest.raises(RemoteAlreadyExistsError):
        service.add_remote("testlocal", "alias", {"remote": str(target_dir)})

    # 5. Test connection
    test_result = service.test_remote("testlocal")
    assert test_result.success is True

    # 6. Delete remote
    service.delete_remote("testlocal")
    assert service.get_remote("testlocal") is None
    assert service.list_remotes() == []

    # 7. Delete non-existent raises RemoteNotFoundError
    with pytest.raises(RemoteNotFoundError):
        service.delete_remote("testlocal")


def test_remote_service_test_nonexistent(tmp_path: Path, rclone_path: Path) -> None:
    config_path = tmp_path / "rclone.conf"
    service = RemoteService(rclone_path, config_path, FakeKeyringStore())
    res = service.test_remote("ghost")
    assert res.success is False
    assert "not found" in res.message.lower()


def test_remote_service_import_config(tmp_path: Path, rclone_path: Path) -> None:
    source_conf = tmp_path / "source.conf"
    source_conf.write_text(
        "[remote_a]\n"
        "type = alias\n"
        "remote = /tmp/dir_a\n\n"
        "[remote_b]\n"
        "type = alias\n"
        "remote = /tmp/dir_b\n",
        encoding="utf-8",
    )

    dest_conf = tmp_path / "dest.conf"
    dest_conf.write_text(
        "[remote_a]\ntype = alias\nremote = /tmp/dir_original\n",
        encoding="utf-8",
    )

    service = RemoteService(rclone_path, dest_conf, FakeKeyringStore())

    # Import without overwrite (remote_a is skipped, remote_b is imported)
    imported = service.import_config(source_conf, overwrite=False)
    assert imported == ["remote_b"]

    remotes = {r.name: r for r in service.list_remotes()}
    assert "remote_a" in remotes
    assert "remote_b" in remotes
    assert remotes["remote_a"].parameters.get("remote") == "/tmp/dir_original"
    assert remotes["remote_b"].parameters.get("remote") == "/tmp/dir_b"

    # Import with overwrite for remote_a
    imported_overwrite = service.import_config(
        source_conf, remote_names=["remote_a"], overwrite=True
    )
    assert imported_overwrite == ["remote_a"]
    remotes = {r.name: r for r in service.list_remotes()}
    assert remotes["remote_a"].parameters.get("remote") == "/tmp/dir_a"


def test_remote_service_import_missing_source(tmp_path: Path, rclone_path: Path) -> None:
    dest_conf = tmp_path / "dest.conf"
    service = RemoteService(rclone_path, dest_conf, FakeKeyringStore())
    with pytest.raises(FileNotFoundError):
        service.import_config(tmp_path / "missing.conf")


def test_remote_service_password_methods(tmp_path: Path, rclone_path: Path) -> None:
    keyring_store = FakeKeyringStore()
    dest_conf = tmp_path / "dest.conf"
    service = RemoteService(rclone_path, dest_conf, keyring_store)

    assert service.has_config_password() is False
    assert service.get_config_password() is None

    service.set_config_password("pass123")
    assert service.has_config_password() is True
    assert service.get_config_password() == "pass123"

    env = service._get_env()
    assert env.get("RCLONE_CONFIG_PASS") == "pass123"

    assert service.remove_config_password() is True
    assert service.has_config_password() is False


def test_cli_remote_workflow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "pontis_rclone.conf"
    target_dir = tmp_path / "clitarget"
    target_dir.mkdir()

    # 1. list empty
    ret = main(["remote", "--rclone-config", str(config_path), "list"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "pontis remote add" in captured.out

    # 2. add remote non-interactive
    ret = main(
        [
            "remote",
            "--rclone-config",
            str(config_path),
            "add",
            "cliremote",
            "alias",
            "--param",
            f"remote={target_dir}",
            "--non-interactive",
        ]
    )
    assert ret == 0
    captured = capsys.readouterr()
    assert "cliremote" in captured.out

    # 3. list has remote
    ret = main(["remote", "--rclone-config", str(config_path), "list"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "cliremote" in captured.out

    # 3b. list JSON
    ret = main(["remote", "--rclone-config", str(config_path), "list", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    assert '"name": "cliremote"' in captured.out

    # 4. test remote
    ret = main(["remote", "--rclone-config", str(config_path), "test", "cliremote"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "cliremote" in captured.out

    # 5. remove remote
    ret = main(["remote", "--rclone-config", str(config_path), "remove", "cliremote"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "cliremote" in captured.out

    # 6. test after remove fails
    ret = main(["remote", "--rclone-config", str(config_path), "test", "cliremote"])
    assert ret == 1


def test_cli_remote_import_and_password(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "pontis_rclone.conf"
    source_conf = tmp_path / "imported.conf"
    source_conf.write_text(
        "[imported_remote]\ntype = alias\nremote = /tmp\n",
        encoding="utf-8",
    )

    # 1. Import
    ret = main(
        [
            "remote",
            "--rclone-config",
            str(config_path),
            "import",
            "--from",
            str(source_conf),
        ]
    )
    assert ret == 0
    captured = capsys.readouterr()
    assert "imported_remote" in captured.out

    # 2. Check it appears in list
    ret = main(["remote", "--rclone-config", str(config_path), "list"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "imported_remote" in captured.out

    # 3. Password commands
    with (
        patch("pontis.infra.keyring_store.keyring.get_password", return_value=None),
        patch("pontis.infra.keyring_store.keyring.set_password") as mock_set,
        patch("pontis.infra.keyring_store.keyring.delete_password") as mock_del,
    ):
        ret = main(["remote", "password", "status"])
        assert ret == 0

        ret = main(["remote", "password", "set", "--password", "supersecret"])
        assert ret == 0
        mock_set.assert_called_once()

        ret = main(["remote", "password", "remove"])
        assert ret == 0
        mock_del.assert_called_once()


def test_remote_service_list_directories(rclone_path: Path, tmp_path: Path) -> None:
    config_path = tmp_path / "rclone.conf"
    keyring_store = FakeKeyringStore()
    svc = RemoteService(binary=rclone_path, config_path=config_path, keyring_store=keyring_store)

    target_dir = tmp_path / "alias_target"
    target_dir.mkdir()
    (target_dir / "FolderB").mkdir()
    (target_dir / "FolderA").mkdir()
    (target_dir / "file.txt").write_text("hello", encoding="utf-8")

    svc.add_remote("myalias", "alias", {"remote": str(target_dir)})

    dirs = svc.list_directories("myalias")
    assert dirs == ["FolderA", "FolderB"]

    with pytest.raises(RemoteNotFoundError):
        svc.list_directories("unknown_remote")
