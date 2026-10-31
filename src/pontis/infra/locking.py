# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-profile run lock, based on an advisory file lock."""

from __future__ import annotations

import fcntl  # POSIX only; a Windows backend (msvcrt) would be added with that port.
import os
from pathlib import Path
from types import TracebackType


class ProfileLockedError(Exception):
    """Raised when another run of the same profile holds the lock."""


class ProfileLock:
    """Non-blocking exclusive lock stored in ``<lock_dir>/profile-<id>.lock``.

    The OS releases the lock if the process dies, so stale locks cannot occur.
    """

    def __init__(self, lock_dir: Path, profile_id: int) -> None:
        lock_dir.mkdir(parents=True, exist_ok=True)
        self._path = lock_dir / f"profile-{profile_id}.lock"
        self._fd: int | None = None
        self._profile_id = profile_id

    def acquire(self) -> None:
        """Take the lock or raise :class:`ProfileLockedError`."""
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            raise ProfileLockedError(str(self._profile_id)) from exc
        self._fd = fd

    def release(self) -> None:
        """Release the lock (idempotent)."""
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> ProfileLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
