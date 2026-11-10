# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for persistent application settings (infra/settings.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pontis.infra.settings import AppSettings, SettingsManager

if TYPE_CHECKING:
    from pathlib import Path


def test_default_settings() -> None:
    """AppSettings has sensible defaults."""
    s = AppSettings()
    assert s.language in ("pt_BR", "en")
    assert s.theme == "system"
    assert s.rclone_path == ""
    assert s.check_updates_on_startup is True
    assert s.ignored_update_version == ""


def test_settings_validation_and_sanitization() -> None:
    """Invalid language or theme are sanitized on validate()."""
    s = AppSettings(language="french", theme="neon")
    s.validate()
    assert s.language == "pt_BR"
    assert s.theme == "system"


def test_settings_manager_load_missing_file(tmp_path: Path) -> None:
    """Loading when the file does not exist yields default settings."""
    cfg_file = tmp_path / "settings.json"
    manager = SettingsManager(cfg_file)
    settings = manager.load()
    assert settings.language == "pt_BR"
    assert settings.theme == "system"


def test_settings_manager_save_and_load(tmp_path: Path) -> None:
    """Settings can be saved and accurately reloaded from disk."""
    cfg_file = tmp_path / "subdir" / "settings.json"
    manager = SettingsManager(cfg_file)

    original = AppSettings(
        language="en",
        theme="dark",
        rclone_path="/opt/bin/rclone",
        check_updates_on_startup=False,
        ignored_update_version="v2.0.0",
        last_update_check="2026-11-10 12:00:00",
    )
    manager.save(original)

    assert cfg_file.is_file()
    loaded = manager.load()
    assert loaded.language == "en"
    assert loaded.theme == "dark"
    assert loaded.rclone_path == "/opt/bin/rclone"
    assert loaded.check_updates_on_startup is False
    assert loaded.ignored_update_version == "v2.0.0"
    assert loaded.last_update_check == "2026-11-10 12:00:00"


def test_settings_manager_corrupted_json(tmp_path: Path) -> None:
    """Corrupted JSON falls back safely to default settings."""
    cfg_file = tmp_path / "settings.json"
    cfg_file.write_text("{invalid json", encoding="utf-8")

    manager = SettingsManager(cfg_file)
    loaded = manager.load()
    assert loaded.language == "pt_BR"
    assert loaded.theme == "system"
