# SPDX-License-Identifier: GPL-3.0-or-later
"""Command-line interface: ``pontis profile``, ``pontis remote`` and ``pontis run``."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from collections.abc import Sequence
from datetime import datetime
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
    ProfileNotFoundError,
    ProfileRepository,
    RunRepository,
)
from pontis.services.import_export_service import (
    ProfileExportError,
    ProfileImportError,
    ProfileTransfer,
    ScriptImporter,
    ScriptImportError,
)
from pontis.services.profile_service import ProfileService
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
from pontis.services.watch_service import WatchService

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
    add.add_argument("--max-delete", type=int, default=25, metavar="COUNT")
    add.add_argument("--check-access", action="store_true")
    add.add_argument("--bwlimit", metavar="RATE")
    add.add_argument("--transfers", type=int)

    psub.add_parser("list", help="List profiles.")
    rem = psub.add_parser("remove", help="Remove a profile (files are never touched).")
    rem.add_argument("name")

    p_export = psub.add_parser("export", help="Export one or all profiles to JSON.")
    p_export.add_argument("name", nargs="?", help="Profile name or ID (or omit with --all).")
    p_export.add_argument("--all", action="store_true", help="Export all profiles.")
    p_export.add_argument("--output", "-o", type=Path, help="File to write JSON to.")

    p_import = psub.add_parser("import", help="Import profiles from a JSON file.")
    p_import.add_argument("file", type=Path, help="JSON file containing profiles.")
    p_import.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing profiles with the same name."
    )
    p_import.add_argument(
        "--rename", action="store_true", help="Rename profiles on conflict (default)."
    )

    p_script = psub.add_parser("import-script", help="Import a profile from a shell sync script.")
    p_script.add_argument("script", type=Path, help="Shell script (e.g. sync.sh).")
    p_script.add_argument("--name", help="Custom name for the imported profile.")

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

    # 4. Watch subcommand
    watch = sub.add_parser("watch", help="Watch local folders and sync on changes with watchdog.")
    watch.add_argument("name", help="Profile name or ID to watch.")
    watch.add_argument(
        "--debounce", type=float, default=5.0, help="Debounce wait time in seconds (default: 5.0)."
    )
    watch.add_argument("--dry-run", action="store_true", help="Run sync in simulation mode.")
    watch.add_argument("--rclone", help="Path to the rclone binary.")
    watch.add_argument(
        "--rclone-config",
        type=Path,
        help="rclone.conf to use (default: the app's own rclone.conf).",
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
                    max_delete_files=args.max_delete,
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

        if args.action == "remove":
            found = repo.get_by_name(args.name)
            if found is None or found.id is None:
                print(tr("profile.not_found", name=args.name), file=sys.stderr)
                return 1
            repo.delete(found.id)
            shutil.rmtree(db_path.parent / "bisync" / str(found.id), ignore_errors=True)
            print(tr("profile.removed", name=found.name))
            return 0

        if args.action == "export":
            profiles_to_export: list[SyncProfile] = []
            if args.all or not args.name:
                profiles_to_export = repo.list()
            else:
                target_p: SyncProfile | None = None
                if args.name.isdigit():
                    try:
                        target_p = repo.get(int(args.name))
                    except ProfileNotFoundError:
                        target_p = None
                if target_p is None:
                    target_p = repo.get_by_name(args.name)

                if target_p is None:
                    print(tr("profile.export_not_found", name=args.name), file=sys.stderr)
                    return 1
                profiles_to_export = [target_p]

            if args.output:
                try:
                    ProfileTransfer.export_to_file(profiles_to_export, args.output)
                except ProfileExportError as err:
                    print(str(err), file=sys.stderr)
                    return 1
                print(tr("profile.exported", count=len(profiles_to_export), path=args.output))
            else:
                print(ProfileTransfer.export_to_json(profiles_to_export))
            return 0

        if args.action == "import":
            try:
                imported_profiles = ProfileTransfer.import_from_file(args.file)
            except ProfileImportError as err:
                print(str(err), file=sys.stderr)
                return 1

            if not imported_profiles:
                print(tr("profile.import_none"))
                return 0

            policy = "overwrite" if args.overwrite else "rename"
            service = ProfileService(conn=conn)
            saved = service.import_profiles(imported_profiles, on_conflict=policy)
            names = ", ".join(p.name for p in saved)
            print(tr("profile.imported_count", count=len(saved), names=names))
            return 0

        if args.action == "import-script":
            try:
                imported_p = ScriptImporter.parse_file(args.script, default_name=args.name)
            except ScriptImportError as err:
                print(tr("script.import_failed", error=err), file=sys.stderr)
                return 1

            service = ProfileService(conn=conn)
            saved_p = service.import_profile(imported_p, on_conflict="rename")
            print(tr("script.imported", name=saved_p.name, path=args.script))
            return 0

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


def _cmd_watch(args: argparse.Namespace, db_path: Path) -> int:
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
        repo = ProfileRepository(conn)
        target_p: SyncProfile | None = None
        if args.name.isdigit():
            try:
                target_p = repo.get(int(args.name))
            except ProfileNotFoundError:
                target_p = None
        if target_p is None:
            target_p = repo.get_by_name(args.name)

        if target_p is None:
            print(tr("profile.not_found", name=args.name), file=sys.stderr)
            return 1

        keyring_store = KeyringStore()
        cfg_pass = keyring_store.get_password()
        env = {"RCLONE_CONFIG_PASS": cfg_pass} if cfg_pass else None

        adapter = RcloneAdapter(info.path, db_path.parent / "bisync", config_path, env=env)
        service = RunService(adapter, RunRepository(conn), db_path.parent / "locks")

        watch_service = WatchService()
        try:
            watchable = WatchService.get_watchable_paths(target_p)
            if not watchable:
                print(tr("watch.no_local", name=target_p.name), file=sys.stderr)
                return 1

            def _on_change(etype: str, fpath: str) -> None:
                t = datetime.now().strftime("%H:%M:%S")
                print(tr("watch.file_changed", time=t, type=etype, path=fpath))

            def _on_sync(p: SyncProfile) -> None:
                t = datetime.now().strftime("%H:%M:%S")
                print(tr("watch.triggering_sync", time=t))
                try:
                    res = service.run(
                        p,
                        dry_run=args.dry_run,
                        require_dry_run_first=False,
                        on_event=_print_event,
                    )
                    t_end = datetime.now().strftime("%H:%M:%S")
                    print(
                        tr(
                            "watch.sync_finished",
                            time=t_end,
                            transferred=res.files_transferred,
                            deleted=res.files_deleted,
                            errors=res.errors,
                        )
                    )
                except Exception as err:
                    print(f"  ! Sync error: {err}", file=sys.stderr)

            paths_str = ", ".join(str(p) for p in watchable)
            print(
                tr(
                    "watch.starting",
                    name=target_p.name,
                    paths=paths_str,
                    debounce=args.debounce,
                )
            )
            watch_service.start_watching(
                target_p,
                debounce_seconds=args.debounce,
                on_change=_on_change,
                on_sync_triggered=_on_sync,
            )

            try:
                while True:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                print(f"\n{tr('watch.stopped')}")
                return 0
        finally:
            watch_service.stop_all()
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
    if args.command == "watch":
        return _cmd_watch(args, db_path)
    return _cmd_run(args, db_path)


if __name__ == "__main__":
    sys.exit(main())
