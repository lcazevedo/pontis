# SPDX-License-Identifier: GPL-3.0-or-later
"""Desktop notifications for Pontis."""

from __future__ import annotations

import contextlib
import shutil
import subprocess

from PySide6.QtWidgets import QSystemTrayIcon


def send_notification(
    title: str,
    message: str,
    *,
    is_error: bool = False,
    tray_icon: QSystemTrayIcon | None = None,
) -> None:
    """Send an OS desktop notification.

    Prefers :class:`QSystemTrayIcon.showMessage` if available, falling back to
    the system ``notify-send`` binary on Linux.
    """
    if tray_icon is not None and QSystemTrayIcon.isSystemTrayAvailable():
        icon_type = (
            QSystemTrayIcon.MessageIcon.Critical
            if is_error
            else QSystemTrayIcon.MessageIcon.Information
        )
        tray_icon.showMessage(title, message, icon_type, 6000)
        return

    notify_send = shutil.which("notify-send")
    if notify_send:
        urgency = "critical" if is_error else "normal"
        with contextlib.suppress(Exception):
            subprocess.Popen(
                [notify_send, "-u", urgency, "-a", "Pontis", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
