# SPDX-License-Identifier: GPL-3.0-or-later
"""Extension point for future schedulers (not implemented in v1)."""

from __future__ import annotations

from typing import Protocol

from pontis.domain.models import SyncProfile


class SchedulerBackend(Protocol):
    """Interface a future scheduler backend (systemd, APScheduler...) must implement."""

    def install(self, profile: SyncProfile) -> None:
        """Register the profile's schedule."""
        ...

    def uninstall(self, profile: SyncProfile) -> None:
        """Remove the profile's schedule."""
        ...
