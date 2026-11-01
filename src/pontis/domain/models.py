# SPDX-License-Identifier: GPL-3.0-or-later
"""Domain models for sync profiles and run results.

These classes are pure data: no Qt, no database and no subprocess access.
Each model knows how to convert itself to and from plain JSON-friendly dicts,
which the storage layer uses to persist nested values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utcnow() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(UTC)


class EndpointKind(StrEnum):
    """Where one side of a sync lives."""

    LOCAL = "local"
    REMOTE = "remote"


class SyncDirection(StrEnum):
    """Direction of a sync profile."""

    BIDIRECTIONAL = "bidirectional"
    A_TO_B = "a_to_b"
    B_TO_A = "b_to_a"


class ConflictPolicy(StrEnum):
    """How bisync resolves a file changed on both sides."""

    KEEP_BOTH = "keep_both"
    NEWER = "newer"
    LARGER = "larger"
    PATH1 = "path1"
    PATH2 = "path2"


class ScheduleKind(StrEnum):
    """Schedule types. Only ``manual`` exists in v1."""

    MANUAL = "manual"


class RunStatus(StrEnum):
    """Final state of a run."""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Endpoint:
    """One side of a sync: a local folder or a path inside an rclone remote."""

    kind: EndpointKind
    path: str
    remote: str | None = None

    def __post_init__(self) -> None:
        if self.kind is EndpointKind.REMOTE and not self.remote:
            raise ValueError("A remote endpoint requires a remote name.")
        if self.kind is EndpointKind.LOCAL and self.remote:
            raise ValueError("A local endpoint cannot have a remote name.")
        if not self.path and self.kind is EndpointKind.LOCAL:
            raise ValueError("A local endpoint requires a path.")

    @classmethod
    def local(cls, path: str) -> Endpoint:
        """Build a local endpoint."""
        return cls(EndpointKind.LOCAL, path)

    @classmethod
    def cloud(cls, remote: str, path: str = "") -> Endpoint:
        """Build an endpoint inside an rclone remote."""
        return cls(EndpointKind.REMOTE, path, remote)

    def to_rclone(self) -> str:
        """Return the rclone path string (``remote:path`` or a local path)."""
        if self.kind is EndpointKind.REMOTE:
            return f"{self.remote}:{self.path}"
        return self.path

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {"kind": self.kind.value, "path": self.path, "remote": self.remote}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Endpoint:
        """Deserialize from :meth:`to_dict` output."""
        return cls(EndpointKind(data["kind"]), data["path"], data.get("remote"))


@dataclass(frozen=True, slots=True)
class SyncOptions:
    """Tunable options of a profile (safe defaults)."""

    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_policy: ConflictPolicy = ConflictPolicy.KEEP_BOTH
    max_delete_percent: int = 50
    check_access: bool = False
    excludes: tuple[str, ...] = ()
    includes: tuple[str, ...] = ()
    bandwidth_limit: str | None = None
    transfers: int | None = None
    extra_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.max_delete_percent <= 100:
            raise ValueError("max_delete_percent must be between 0 and 100.")
        if self.transfers is not None and self.transfers < 1:
            raise ValueError("transfers must be at least 1.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "direction": self.direction.value,
            "conflict_policy": self.conflict_policy.value,
            "max_delete_percent": self.max_delete_percent,
            "check_access": self.check_access,
            "excludes": list(self.excludes),
            "includes": list(self.includes),
            "bandwidth_limit": self.bandwidth_limit,
            "transfers": self.transfers,
            "extra_flags": list(self.extra_flags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncOptions:
        """Deserialize; missing keys fall back to defaults."""
        defaults = cls()
        return cls(
            direction=SyncDirection(data.get("direction", defaults.direction)),
            conflict_policy=ConflictPolicy(data.get("conflict_policy", defaults.conflict_policy)),
            max_delete_percent=data.get("max_delete_percent", defaults.max_delete_percent),
            check_access=data.get("check_access", defaults.check_access),
            excludes=tuple(data.get("excludes", ())),
            includes=tuple(data.get("includes", ())),
            bandwidth_limit=data.get("bandwidth_limit"),
            transfers=data.get("transfers"),
            extra_flags=tuple(data.get("extra_flags", ())),
        )


@dataclass(frozen=True, slots=True)
class Schedule:
    """Profile schedule. v1 only supports ``manual``; reserved for the future."""

    kind: ScheduleKind = ScheduleKind.MANUAL

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {"kind": self.kind.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Schedule:
        """Deserialize from :meth:`to_dict` output."""
        return cls(ScheduleKind(data.get("kind", ScheduleKind.MANUAL)))


@dataclass(slots=True)
class SyncProfile:
    """A named pair of endpoints plus options."""

    name: str
    side_a: Endpoint
    side_b: Endpoint
    options: SyncOptions = field(default_factory=SyncOptions)
    schedule: Schedule = field(default_factory=Schedule)
    id: int | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Profile name must not be empty.")


@dataclass(slots=True)
class RunResult:
    """Outcome of one execution of a profile."""

    profile_id: int
    started_at: datetime = field(default_factory=utcnow)
    status: RunStatus = RunStatus.RUNNING
    dry_run: bool = False
    finished_at: datetime | None = None
    files_transferred: int = 0
    files_deleted: int = 0
    errors: int = 0
    message: str = ""
    id: int | None = None


@dataclass(frozen=True, slots=True)
class RemoteInfo:
    """A configured cloud remote in rclone."""

    name: str
    type: str
    parameters: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "name": self.name,
            "type": self.type,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RemoteInfo:
        """Deserialize from :meth:`to_dict` output."""
        return cls(
            name=str(data["name"]),
            type=str(data.get("type", "")),
            parameters={str(k): str(v) for k, v in data.get("parameters", {}).items()},
        )


@dataclass(frozen=True, slots=True)
class RemoteTestResult:
    """Outcome of testing a remote connection."""

    remote: str
    success: bool
    message: str = ""
    storage_info: dict[str, Any] | None = None
