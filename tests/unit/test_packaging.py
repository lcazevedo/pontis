# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for Linux packaging assets and frozen subprocess environment safety."""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from pontis.infra.rclone import clean_subprocess_env

if TYPE_CHECKING:
    import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]


def test_clean_subprocess_env_unfrozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """When not frozen, clean_subprocess_env keeps LD_LIBRARY_PATH untouched."""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/custom/lib")

    env = clean_subprocess_env({"RCLONE_CONFIG_PASS": "secret"})
    assert env["LD_LIBRARY_PATH"] == "/custom/lib"
    assert env["RCLONE_CONFIG_PASS"] == "secret"


def test_clean_subprocess_env_frozen_restores_orig(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frozen bundle restores LD_LIBRARY_PATH_ORIG when present."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI12345")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/local/lib")

    env = clean_subprocess_env()
    assert env["LD_LIBRARY_PATH"] == "/usr/local/lib"


def test_clean_subprocess_env_frozen_removes_pyinstaller_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Frozen bundle removes PyInstaller LD_LIBRARY_PATH when no original was set."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI12345")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)

    env = clean_subprocess_env()
    assert "LD_LIBRARY_PATH" not in env


def test_packaging_files_and_metadata_valid() -> None:
    """Linux packaging manifests, icons, desktop entry, and scripts exist and are valid."""
    packaging = ROOT_DIR / "packaging"
    linux = packaging / "linux"
    flatpak = packaging / "flatpak"

    assert (packaging / "pyinstaller.spec").is_file()
    assert (packaging / "pyinstaller_entry.py").is_file()

    for script_name in ("AppRun", "build_appimage.sh", "test_appimage_in_docker.sh"):
        script = linux / script_name
        assert script.is_file()
        assert os.access(script, os.X_OK), f"{script_name} must be executable"

    desktop = (linux / "io.github.lcazevedo.Pontis.desktop").read_text(encoding="utf-8")
    assert "[Desktop Entry]" in desktop
    assert "Type=Application" in desktop
    assert "Name=Pontis" in desktop
    assert "Icon=io.github.lcazevedo.Pontis" in desktop
    assert "Exec=pontis" in desktop

    metainfo_path = linux / "io.github.lcazevedo.Pontis.metainfo.xml"
    tree = ET.parse(metainfo_path)
    root = tree.getroot()
    assert root.findtext("id") == "io.github.lcazevedo.Pontis"
    assert root.findtext("project_license") == "GPL-3.0-or-later"
    assert root.findtext("name") == "Pontis"

    svg = linux / "io.github.lcazevedo.Pontis.svg"
    png = linux / "io.github.lcazevedo.Pontis.png"
    assert svg.is_file() and svg.stat().st_size > 0
    assert png.is_file() and png.stat().st_size > 0

    flatpak_manifest = (flatpak / "io.github.lcazevedo.Pontis.yml").read_text(encoding="utf-8")
    assert "app-id: io.github.lcazevedo.Pontis" in flatpak_manifest
    assert "command: pontis" in flatpak_manifest
