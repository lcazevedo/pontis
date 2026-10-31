# SPDX-License-Identifier: GPL-3.0-or-later
"""Command-line interface: ``pontis profile ...`` and ``pontis run``."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from pontis.domain.models import (
    ConflictPolicy,
    Endpoint,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)
from pontis.i18n import tr
from pontis.infra.database import connect
from pontis.infra.locking import ProfileLockedError
from pontis.infra.paths import config_dir, default_db_path
from pontis.infra.rclone import (
    RcloneNotFoundError,
    RcloneTooOldError,
    format_version,
    locate_rclone,
)
from pontis.infra.rclone_adapter import LogEvent, RcloneAdapter
from pontis.infra.repositories import (
    DuplicateProfileError,
    ProfileRepository,
    RunRepository,
)
from pontis.services.run_service import (
    EndpointMissingError,
    FirstRunDryRunRequiredError,
    RunService,
)

_REMOTE_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.\- ]*):(.*)$")


def parse_endpoint(spec: str) -> Endpoint:
    """Parse ``remote:path`` as a cloud endpoint, anything else as a local path."""
    match = _REMOTE_RE.match(spec)
    if match and not spec.startswith(("/", ".", "~")):
        return Endpoint.cloud(match.group(1), match.group(2))
    return Endpoint.local(str(Path(spec).expanduser().resolve()))


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="pontis", description="Pontis: sync folders with rclone.")
    parser.add_argument("--db", type=Path, help="SQLite database path (default: app data dir).")
    sub = parser.add_subparsers(dest="command")

    profile = sub.add_parser("profile", help="Manage sync profiles.")
    psub = profile.add_subparsers(dest="action", required=True)

    add = psub.add_parser("add", help="Create a profile.")
    add.add_argument("name")
    add.add_argument("--a", dest="side_a", required=True, help="Side A: local path or remote:path.")
    add.add_argument("--b", dest="side_b", required=True, help="Side B: local path or remote:path.")
    add.add_argument(
        "--direction", choices=[d.value for d in SyncDirection], default="bidirectional"
    )
    add.add_argument("--conflict", choices=[c.value for c in ConflictPolicy], default="keep_both")
    add.add_argument("--exclude", action="append", default=[], metavar="PATTERN")
    add.add_argument("--include", action="append", default=[], metavar="PATTERN")
    add.add_argument("--max-delete", type=int, default=50, metavar="PERCENT")
    add.add_argument("--check-access", action="store_true")
    add.add_argument("--bwlimit", metavar="RATE")
    add.add_argument("--transfers", type=int)

    psub.add_parser("list", help="List profiles.")
    rem = psub.add_parser("remove", help="Remove a profile (files are never touched).")
    rem.add_argument("name")

    run = sub.add_parser("run", help="Run a profile.")
    run.add_argument("name")
    run.add_argument("--dry-run", action="store_true", help="Simulate without changing anything.")
    run.add_argument("--rclone", help="Path to the rclone binary.")
    run.add_argument(
        "--rclone-config",
        type=Path,
        help="rclone.conf to use (default: the app's own rclone.conf).",
    )
    run.add_argument(
        "--skip-first-dry-run",
        action="store_true",
        help="Allow the first real run without a prior successful --dry-run.",
    )
    return parser


def _print_event(event: LogEvent) -> None:
    if event.level in ("error", "critical"):
        print(f"  ! {event.message}", file=sys.stderr)
    elif (
        event.message.startswith("- ")
        or event.obj
        and event.message.startswith(("Copied", "Deleted", "Updated"))
    ):
        suffix = f" {event.obj}" if event.obj else ""
        print(f"  {event.message}{suffix}")


def _cmd_profile(args: argparse.Namespace, db_path: Path) -> int:
    conn = connect(db_path)
    repo = ProfileRepository(conn)
    try:
        if args.action == "add":
            try:
                options = SyncOptions(
                    direction=SyncDirection(args.direction),
                    conflict_policy=ConflictPolicy(args.conflict),
                    max_delete_percent=args.max_delete,
                    check_access=args.check_access,
                    excludes=tuple(args.exclude),
                    includes=tuple(args.include),
                    bandwidth_limit=args.bwlimit,
                    transfers=args.transfers,
                )
                profile = SyncProfile(
                    args.name,
                    parse_endpoint(args.side_a),
                    parse_endpoint(args.side_b),
                    options,
                )
            except ValueError as exc:
                print(tr("profile.invalid", error=exc), file=sys.stderr)
                return 2
            try:
                repo.add(profile)
            except DuplicateProfileError:
                print(tr("profile.duplicate", name=args.name), file=sys.stderr)
                return 1
            print(tr("profile.added", name=profile.name, id=profile.id))
            return 0

        if args.action == "list":
            profiles = repo.list()
            if not profiles:
                print(tr("profile.none"))
                return 0
            for p in profiles:
                arrow = tr(f"profile.direction.{p.options.direction.value}")
                print(f"{p.id}\t{p.name}\t{p.side_a.to_rclone()} {arrow} {p.side_b.to_rclone()}")
            return 0

        # remove
        found = repo.get_by_name(args.name)
        if found is None or found.id is None:
            print(tr("profile.not_found", name=args.name), file=sys.stderr)
            return 1
        repo.delete(found.id)
        shutil.rmtree(db_path.parent / "bisync" / str(found.id), ignore_errors=True)
        print(tr("profile.removed", name=found.name))
        return 0
    finally:
        conn.close()


def _cmd_run(args: argparse.Namespace, db_path: Path) -> int:
    try:
        info = locate_rclone(args.rclone)
    except RcloneNotFoundError:
        print(tr("rclone.not_found"), file=sys.stderr)
        return 3
    except RcloneTooOldError as exc:
        print(
            tr(
                "rclone.too_old",
                found=format_version(exc.found),
                minimum=format_version(exc.minimum),
            ),
            file=sys.stderr,
        )
        return 3

    config_path: Path = args.rclone_config or (config_dir() / "rclone.conf")
    if args.rclone_config and not config_path.is_file():
        print(tr("rclone.config_missing", path=config_path), file=sys.stderr)
        return 3

    conn = connect(db_path)
    try:
        profile = ProfileRepository(conn).get_by_name(args.name)
        if profile is None:
            print(tr("profile.not_found", name=args.name), file=sys.stderr)
            return 1
        adapter = RcloneAdapter(info.path, db_path.parent / "bisync", config_path)
        service = RunService(adapter, RunRepository(conn), db_path.parent / "locks")
        mode = tr("run.mode_dry") if args.dry_run else ""
        print(tr("run.starting", name=profile.name, mode=mode))
        if adapter.needs_resync(profile):
            print(tr("run.first_sync"))
        try:
            result = service.run(
                profile,
                dry_run=args.dry_run,
                require_dry_run_first=not args.skip_first_dry_run,
                on_event=_print_event,
            )
        except ProfileLockedError:
            print(tr("run.locked", name=profile.name), file=sys.stderr)
            return 4
        except EndpointMissingError as exc:
            print(tr("run.missing_dir", path=exc.path), file=sys.stderr)
            return 4
        except FirstRunDryRunRequiredError:
            print(tr("run.first_dry_required", name=profile.name), file=sys.stderr)
            return 4
        except ValueError as exc:
            print(tr("error.flag", error=exc), file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            print(tr("run.cancelled"), file=sys.stderr)
            return 130

        if result.status.value == "success":
            key = "run.success_dry" if args.dry_run else "run.success"
            print(
                tr(
                    key,
                    transferred=result.files_transferred,
                    deleted=result.files_deleted,
                    errors=result.errors,
                )
            )
            return 0
        print(tr("run.failed", message=result.message), file=sys.stderr)
        if "--resync" in result.message:
            print(tr("run.needs_resync"), file=sys.stderr)
        return 1
    finally:
        conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    db_path: Path = args.db or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if args.command == "profile":
        return _cmd_profile(args, db_path)
    return _cmd_run(args, db_path)
