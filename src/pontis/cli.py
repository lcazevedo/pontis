# SPDX-License-Identifier: GPL-3.0-or-later
"""Command-line interface: ``pontis profile``, ``pontis remote`` and ``pontis run``."""

from __future__ import annotations

import argparse
import json
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
from pontis.infra.keyring_store import KeyringStore
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
from pontis.services.remote_service import (
    RemoteAlreadyExistsError,
    RemoteInvalidNameError,
    RemoteNotFoundError,
    RemoteOperationError,
    RemoteService,
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


def format_bytes(num_bytes: int | float | None) -> str:
    """Format a byte count into a human-readable string (e.g. 1.50 GiB)."""
    if num_bytes is None:
        return "N/A"
    n = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024.0 or unit == "TiB":
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} PiB"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="pontis", description="Pontis: sync folders with rclone.")
    parser.add_argument("--db", type=Path, help="SQLite database path (default: app data dir).")
    sub = parser.add_subparsers(dest="command")

    # 1. Profile subcommands
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

    # 2. Remote subcommands
    remote = sub.add_parser("remote", help="Manage cloud remotes.")
    remote.add_argument("--rclone", help="Path to the rclone binary.")
    remote.add_argument(
        "--rclone-config",
        type=Path,
        help="rclone.conf to use (default: the app's own rclone.conf).",
    )
    rsub = remote.add_subparsers(dest="action", required=True)

    r_list = rsub.add_parser("list", help="List configured remotes.")
    r_list.add_argument("--json", action="store_true", help="Output as JSON.")

    r_add = rsub.add_parser("add", help="Configure a new cloud remote.")
    r_add.add_argument("name", help="Name of the remote (e.g. gdrive).")
    r_add.add_argument("type", help="Remote type (e.g. drive, onedrive, dropbox, alias).")
    r_add.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Option passed to rclone config create.",
    )
    r_add.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not start interactive OAuth in a browser.",
    )

    r_test = rsub.add_parser("test", help="Test connectivity to a remote.")
    r_test.add_argument("name", help="Remote name to test.")
    r_test.add_argument("--path", default="", help="Subfolder path to test against.")

    r_remove = rsub.add_parser("remove", help="Remove a remote from configuration.")
    r_remove.add_argument("name", help="Remote name to remove.")

    r_import = rsub.add_parser("import", help="Import remotes from an existing rclone.conf.")
    r_import.add_argument(
        "--from",
        dest="source",
        type=Path,
        help="Source config path (default: ~/.config/rclone/rclone.conf).",
    )
    r_import.add_argument("--remote", help="Name of a single remote to import.")
    r_import.add_argument(
        "--overwrite", action="store_true", help="Overwrite if remote already exists."
    )
    r_import.add_argument(
        "--source-password", help="Password for decrypting source config file if encrypted."
    )

    r_pwd = rsub.add_parser("password", help="Manage configuration password in keyring.")
    psub_pwd = r_pwd.add_subparsers(dest="password_action", required=True)
    p_set = psub_pwd.add_parser("set", help="Save config password in keyring.")
    p_set.add_argument("--password", help="Password string (prompts securely if omitted).")
    psub_pwd.add_parser("remove", help="Remove config password from keyring.")
    psub_pwd.add_parser("status", help="Check if config password is set in keyring.")

    # 3. Run subcommand
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


def _cmd_remote(args: argparse.Namespace) -> int:
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
    keyring_store = KeyringStore()
    service = RemoteService(info.path, config_path, keyring_store)

    if args.action == "list":
        remotes = service.list_remotes()
        if not remotes:
            print(tr("remote.none"))
            return 0
        if args.json:
            print(json.dumps([r.to_dict() for r in remotes], indent=2))
            return 0
        for r in remotes:
            print(f"{r.name}\t{r.type}")
        return 0

    if args.action == "add":
        params: dict[str, str] = {}
        for p in args.param:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k.strip()] = v.strip()
            else:
                params[p.strip()] = "true"
        try:
            created = service.add_remote(
                args.name,
                args.type,
                params if params else None,
                interactive=not args.non_interactive,
            )
            print(tr("remote.added", name=created.name, type=created.type))
            return 0
        except RemoteInvalidNameError:
            print(tr("remote.invalid_name", name=args.name), file=sys.stderr)
            return 2
        except RemoteAlreadyExistsError:
            print(tr("remote.duplicate", name=args.name), file=sys.stderr)
            return 1
        except RemoteOperationError as exc:
            print(tr("remote.operation_failed", error=exc), file=sys.stderr)
            return 1

    if args.action == "test":
        result = service.test_remote(args.name, path=args.path)
        if result.success:
            if result.storage_info:
                total = format_bytes(result.storage_info.get("total"))
                used = format_bytes(result.storage_info.get("used"))
                free = format_bytes(result.storage_info.get("free"))
                print(
                    tr(
                        "remote.test_success_storage",
                        name=result.remote,
                        total=total,
                        used=used,
                        free=free,
                    )
                )
            else:
                print(tr("remote.test_success", name=result.remote))
            return 0
        print(tr("remote.test_failed", name=result.remote, message=result.message), file=sys.stderr)
        return 1

    if args.action == "remove":
        try:
            service.delete_remote(args.name)
            print(tr("remote.removed", name=args.name))
            return 0
        except RemoteNotFoundError:
            print(tr("remote.not_found", name=args.name), file=sys.stderr)
            return 1
        except RemoteOperationError as exc:
            print(tr("remote.operation_failed", error=exc), file=sys.stderr)
            return 1

    if args.action == "import":
        source_path = args.source or (Path.home() / ".config" / "rclone" / "rclone.conf")
        try:
            remote_names = [args.remote] if args.remote else None
            imported = service.import_config(
                source_path,
                remote_names=remote_names,
                overwrite=args.overwrite,
                source_password=args.source_password,
            )
            if not imported:
                print(tr("remote.import_none"))
                return 0
            print(tr("remote.imported", count=len(imported), names=", ".join(imported)))
            return 0
        except FileNotFoundError:
            print(tr("remote.import_source_not_found", path=source_path), file=sys.stderr)
            return 1
        except RemoteNotFoundError:
            print(tr("remote.not_found", name=args.remote), file=sys.stderr)
            return 1
        except RemoteOperationError as exc:
            print(tr("remote.operation_failed", error=exc), file=sys.stderr)
            return 1

    if args.action == "password":
        if args.password_action == "set":
            pwd = args.password
            if not pwd:
                import getpass

                pwd = getpass.getpass("Password: ")
            service.set_config_password(pwd)
            print(tr("remote.password_set"))
            return 0
        if args.password_action == "remove":
            service.remove_config_password()
            print(tr("remote.password_removed"))
            return 0
        if args.password_action == "status":
            if service.has_config_password():
                print(tr("remote.password_status_set"))
            else:
                print(tr("remote.password_status_not_set"))
            return 0

    return 2


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

        keyring_store = KeyringStore()
        cfg_pass = keyring_store.get_password()
        env = {"RCLONE_CONFIG_PASS": cfg_pass} if cfg_pass else None

        adapter = RcloneAdapter(info.path, db_path.parent / "bisync", config_path, env=env)
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
    if args.command == "remote":
        return _cmd_remote(args)
    db_path: Path = args.db or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if args.command == "profile":
        return _cmd_profile(args, db_path)
    return _cmd_run(args, db_path)


if __name__ == "__main__":
    sys.exit(main())
