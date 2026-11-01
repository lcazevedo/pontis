# SPDX-License-Identifier: GPL-3.0-or-later
"""Service for managing cloud remotes inside the app's own rclone.conf."""

from __future__ import annotations

import configparser
import json
import os
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pontis.domain.models import RemoteInfo, RemoteTestResult
from pontis.infra.keyring_store import KeyringStore

_REMOTE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\- ]*$")


class RemoteServiceError(Exception):
    """Base exception for remote management errors."""


class RemoteNotFoundError(RemoteServiceError):
    """Raised when a specified remote does not exist."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class RemoteAlreadyExistsError(RemoteServiceError):
    """Raised when attempting to create a remote that already exists."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class RemoteInvalidNameError(RemoteServiceError):
    """Raised when a remote name has invalid characters or format."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class RemoteOperationError(RemoteServiceError):
    """Raised when an underlying rclone command fails."""


def validate_remote_name(name: str) -> None:
    """Validate that a remote name matches rclone's conventions."""
    if not name or ":" in name or not _REMOTE_NAME_RE.match(name):
        raise RemoteInvalidNameError(name)


class RemoteService:
    """Manages cloud remotes within Pontis's private rclone configuration."""

    def __init__(
        self,
        binary: Path | str,
        config_path: Path,
        keyring_store: KeyringStore | None = None,
    ) -> None:
        self.binary = Path(binary)
        self.config_path = config_path
        self.keyring_store = keyring_store or KeyringStore()

    def _get_env(self, extra_env: dict[str, str] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        password = self.keyring_store.get_password()
        if password:
            env["RCLONE_CONFIG_PASS"] = password
        return env

    def list_remotes(self) -> list[RemoteInfo]:
        """List all configured remotes in the app's rclone.conf.

        Returns an empty list if the config file does not exist yet.
        """
        if not self.config_path.is_file():
            return []

        cmd = [str(self.binary), "config", "dump", "--config", str(self.config_path)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=self._get_env(),
                check=False,
            )
        except OSError as exc:
            raise RemoteOperationError(str(exc)) from exc

        if proc.returncode != 0:
            if "not found" in proc.stderr.lower():
                return []
            raise RemoteOperationError(proc.stderr.strip() or f"rclone exit {proc.returncode}")

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RemoteOperationError(f"Failed to parse rclone config dump: {exc}") from exc

        if not isinstance(data, dict):
            return []

        remotes: list[RemoteInfo] = []
        for name, params in data.items():
            if isinstance(params, dict):
                remotes.append(
                    RemoteInfo(
                        name=name,
                        type=str(params.get("type", "unknown")),
                        parameters={str(k): str(v) for k, v in params.items()},
                    )
                )
        remotes.sort(key=lambda r: r.name)
        return remotes

    def get_remote(self, name: str) -> RemoteInfo | None:
        """Find a remote by name, or return ``None``."""
        for r in self.list_remotes():
            if r.name == name:
                return r
        return None

    def add_remote(
        self,
        name: str,
        type: str,
        parameters: dict[str, str] | None = None,
        *,
        interactive: bool = False,
    ) -> RemoteInfo:
        """Create a new remote in the app's rclone.conf.

        If ``interactive=True``, stdin/stdout/stderr are connected so rclone can
        perform the interactive OAuth browser authorization.
        """
        validate_remote_name(name)
        if self.get_remote(name) is not None:
            raise RemoteAlreadyExistsError(name)

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(self.binary), "config", "create", name, type]
        if parameters:
            for k, v in parameters.items():
                cmd.extend([str(k), str(v)])
        cmd.extend(["--config", str(self.config_path)])

        env = self._get_env()

        try:
            if interactive:
                proc = subprocess.run(cmd, env=env, text=True, check=False)
            else:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                )
        except OSError as exc:
            raise RemoteOperationError(str(exc)) from exc

        if proc.returncode != 0:
            err_msg = "" if interactive else getattr(proc, "stderr", "").strip()
            raise RemoteOperationError(err_msg or f"rclone exit {proc.returncode}")

        if self.config_path.is_file():
            self.config_path.chmod(0o600)

        created = self.get_remote(name)
        if created is None:
            raise RemoteOperationError(f"Remote '{name}' was not created.")
        return created

    def delete_remote(self, name: str) -> None:
        """Remove a remote from the app's rclone.conf."""
        if self.get_remote(name) is None:
            raise RemoteNotFoundError(name)

        cmd = [str(self.binary), "config", "delete", name, "--config", str(self.config_path)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=self._get_env(),
                check=False,
            )
        except OSError as exc:
            raise RemoteOperationError(str(exc)) from exc

        if proc.returncode != 0:
            raise RemoteOperationError(proc.stderr.strip() or f"rclone exit {proc.returncode}")

    def test_remote(self, name: str, path: str = "") -> RemoteTestResult:
        """Test connectivity and quota with a remote."""
        if self.get_remote(name) is None:
            return RemoteTestResult(
                remote=name,
                success=False,
                message=f"Remote '{name}' not found.",
            )

        target = f"{name}:{path}"
        env = self._get_env()

        # 1. Try 'rclone about <remote>: --json' to get quota and verify auth
        about_cmd = [str(self.binary), "about", target, "--json", "--config", str(self.config_path)]
        try:
            proc = subprocess.run(
                about_cmd,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
        except OSError as exc:
            return RemoteTestResult(remote=name, success=False, message=str(exc))

        if proc.returncode == 0:
            storage_info: dict[str, Any] | None = None
            try:
                data = json.loads(proc.stdout)
                if isinstance(data, dict):
                    storage_info = data
            except json.JSONDecodeError:
                pass
            return RemoteTestResult(remote=name, success=True, storage_info=storage_info)

        # 2. If 'about' is not supported by the backend, fallback to 'rclone lsf --max-depth 1'
        err_lower = proc.stderr.lower()
        if "not supported" in err_lower or "command about" in err_lower:
            lsf_cmd = [
                str(self.binary),
                "lsf",
                target,
                "--max-depth",
                "1",
                "--config",
                str(self.config_path),
            ]
            try:
                proc_lsf = subprocess.run(
                    lsf_cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    check=False,
                )
            except OSError as exc:
                return RemoteTestResult(remote=name, success=False, message=str(exc))

            if proc_lsf.returncode == 0:
                return RemoteTestResult(
                    remote=name,
                    success=True,
                    message="Connected successfully.",
                )
            return RemoteTestResult(
                remote=name,
                success=False,
                message=proc_lsf.stderr.strip() or f"rclone exit {proc_lsf.returncode}",
            )

        return RemoteTestResult(
            remote=name,
            success=False,
            message=proc.stderr.strip() or f"rclone exit {proc.returncode}",
        )

    def import_config(
        self,
        source_path: Path,
        remote_names: Sequence[str] | None = None,
        *,
        overwrite: bool = False,
        source_password: str | None = None,
    ) -> list[str]:
        """Import remotes from another rclone.conf into the app's configuration.

        Returns a list of successfully imported remote names.
        """
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(str(source))

        source_env = os.environ.copy()
        if source_password:
            source_env["RCLONE_CONFIG_PASS"] = source_password
        elif self.keyring_store.has_password():
            pwd = self.keyring_store.get_password()
            if pwd:
                source_env["RCLONE_CONFIG_PASS"] = pwd

        # Read decrypted source config via 'rclone config show'
        cmd_show = [str(self.binary), "config", "show", "--config", str(source)]
        try:
            proc = subprocess.run(
                cmd_show,
                capture_output=True,
                text=True,
                env=source_env,
                check=False,
            )
        except OSError as exc:
            raise RemoteOperationError(str(exc)) from exc

        if proc.returncode != 0:
            raise RemoteOperationError(
                proc.stderr.strip() or f"Failed to read source config (exit {proc.returncode})"
            )

        source_parser = configparser.RawConfigParser()
        try:
            source_parser.read_string(proc.stdout)
        except configparser.Error as exc:
            raise RemoteOperationError(f"Failed to parse source config: {exc}") from exc

        all_source_sections = source_parser.sections()
        if remote_names is not None:
            missing = [name for name in remote_names if name not in all_source_sections]
            if missing:
                raise RemoteNotFoundError(missing[0])
            target_sections = [name for name in remote_names if name in all_source_sections]
        else:
            target_sections = all_source_sections

        # Read destination config (or start empty)
        dest_parser = configparser.RawConfigParser()
        if self.config_path.is_file():
            dest_show = [
                str(self.binary),
                "config",
                "show",
                "--config",
                str(self.config_path),
            ]
            try:
                proc_dest = subprocess.run(
                    dest_show,
                    capture_output=True,
                    text=True,
                    env=self._get_env(),
                    check=False,
                )
                if proc_dest.returncode == 0:
                    dest_parser.read_string(proc_dest.stdout)
            except (OSError, configparser.Error):
                pass

        imported: list[str] = []
        for name in target_sections:
            if dest_parser.has_section(name) and not overwrite:
                continue
            if not dest_parser.has_section(name):
                dest_parser.add_section(name)
            for k, v in source_parser.items(name):
                dest_parser.set(name, k, v)
            imported.append(name)

        if imported:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                dest_parser.write(f)
            self.config_path.chmod(0o600)

        return imported

    def get_config_password(self) -> str | None:
        """Get the config password stored in the keyring."""
        return self.keyring_store.get_password()

    def set_config_password(self, password: str) -> None:
        """Save the config password to the keyring."""
        self.keyring_store.set_password(password)

    def remove_config_password(self) -> bool:
        """Remove the config password from the keyring."""
        return self.keyring_store.delete_password()

    def has_config_password(self) -> bool:
        """Check whether a config password is saved in the keyring."""
        return self.keyring_store.has_password()
