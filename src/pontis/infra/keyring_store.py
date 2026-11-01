# SPDX-License-Identifier: GPL-3.0-or-later
"""Keyring integration for storing credentials and configuration passwords."""

from __future__ import annotations

import logging

import keyring
import keyring.errors

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_NAME = "pontis"
KEY_RCLONE_CONFIG_PASS = "rclone_config_pass"


class KeyringStore:
    """Wrapper around the system keyring for Pontis secrets."""

    def __init__(self, service_name: str = DEFAULT_SERVICE_NAME) -> None:
        self.service_name = service_name

    def get_password(self, username: str = KEY_RCLONE_CONFIG_PASS) -> str | None:
        """Retrieve a stored password, or ``None`` if not found or on error."""
        try:
            return keyring.get_password(self.service_name, username)
        except keyring.errors.KeyringError as exc:
            logger.warning("Failed to get password from keyring: %s", exc)
            return None

    def set_password(self, password: str, username: str = KEY_RCLONE_CONFIG_PASS) -> None:
        """Store a password in the keyring.

        Raises :class:`keyring.errors.KeyringError` if the backend fails.
        """
        keyring.set_password(self.service_name, username, password)

    def delete_password(self, username: str = KEY_RCLONE_CONFIG_PASS) -> bool:
        """Remove a password from the keyring.

        Returns ``True`` if removed, ``False`` if it was not found or failed.
        """
        try:
            keyring.delete_password(self.service_name, username)
            return True
        except (keyring.errors.PasswordDeleteError, keyring.errors.KeyringError) as exc:
            logger.debug("Password not found or could not be deleted: %s", exc)
            return False

    def has_password(self, username: str = KEY_RCLONE_CONFIG_PASS) -> bool:
        """Check whether a password is set in the keyring."""
        return self.get_password(username) is not None
