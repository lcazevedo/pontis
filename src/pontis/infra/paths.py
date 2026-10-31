# SPDX-License-Identifier: GPL-3.0-or-later
"""Application directories, resolved through ``platformdirs``."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_path, user_data_path, user_log_path

APP_NAME = "pontis"


def data_dir() -> Path:
    """Directory for the database and app state."""
    return user_data_path(APP_NAME, ensure_exists=True)


def config_dir() -> Path:
    """Directory for the app's own configuration (e.g. its rclone.conf)."""
    return user_config_path(APP_NAME, ensure_exists=True)


def log_dir() -> Path:
    """Directory for rotating logs."""
    return user_log_path(APP_NAME, ensure_exists=True)


def default_db_path() -> Path:
    """Default location of the SQLite database."""
    return data_dir() / "pontis.db"
