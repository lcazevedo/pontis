# SPDX-License-Identifier: GPL-3.0-or-later
"""Import and export services for sync profiles and shell scripts.

Allows exporting and importing profiles in JSON format without credentials,
and parsing shell scripts (such as ``sync.sh``) that invoke rclone bisync/sync
into equivalent :class:`SyncProfile` instances.
"""

from __future__ import annotations

import contextlib
import json
import re
import shlex
from pathlib import Path
from typing import Any

from pontis.domain.models import (
    ConflictPolicy,
    Endpoint,
    Schedule,
    SyncDirection,
    SyncOptions,
    SyncProfile,
)


class ScriptImportError(Exception):
    """Raised when a shell script cannot be parsed into a sync profile."""


class ProfileExportError(Exception):
    """Raised when exporting profiles fails."""


class ProfileImportError(Exception):
    """Raised when importing profile JSON data fails."""


_SHELL_VAR_ASSIGN_RE = re.compile(
    r"""^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=((?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|[^\s;#]*))"""
)
_VAR_INTERPOLATION_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_REMOTE_SPEC_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.\- ]*):(.*)$")

# Flags that are controlled internally or shouldn't be added to extra_flags
_MANAGED_FLAGS = {
    "--resync",
    "--verbose",
    "-v",
    "--quiet",
    "-q",
    "--dry-run",
    "--use-json-log",
    "--stats",
    "--config",
    "--workdir",
}


def _expand_shell_vars(value: str, variables: dict[str, str]) -> str:
    """Replace $VAR and ${VAR} occurrences using known variables."""

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1) or match.group(2)
        return variables.get(var_name, match.group(0))

    # Expand recursively up to 5 times for nested references
    current = value
    for _ in range(5):
        expanded = _VAR_INTERPOLATION_RE.sub(_replace, current)
        if expanded == current:
            break
        current = expanded
    return current


def _parse_endpoint_spec(spec: str) -> Endpoint:
    """Parse a path string into a local or remote Endpoint."""
    clean_spec = spec.strip()
    match = _REMOTE_SPEC_RE.match(clean_spec)
    if match and not clean_spec.startswith(("/", ".", "~")):
        remote_name = match.group(1)
        remote_path = match.group(2)
        return Endpoint.cloud(remote_name, remote_path)
    # Local path
    return Endpoint.local(str(Path(clean_spec).expanduser()))


class ScriptImporter:
    """Parser for shell scripts that invoke ``rclone bisync`` or ``rclone sync``."""

    @classmethod
    def parse_file(cls, script_path: Path | str, default_name: str | None = None) -> SyncProfile:
        """Read a shell script file and parse it into a :class:`SyncProfile`."""
        path = Path(script_path)
        if not path.is_file():
            raise ScriptImportError(f"Script file not found: {path}")
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as err:
            raise ScriptImportError(f"Failed to read script file '{path}': {err}") from err
        name = default_name or path.stem
        return cls.parse_text(content, default_name=name)

    @classmethod
    def parse_text(cls, content: str, default_name: str | None = None) -> SyncProfile:
        """Parse shell script contents and return an unpersisted :class:`SyncProfile`."""
        variables: dict[str, str] = {}
        # First normalize line continuations with backslashes
        normalized_lines: list[str] = []
        continuation = ""
        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            if line.endswith("\\"):
                continuation += line[:-1] + " "
            else:
                combined = continuation + line
                continuation = ""
                normalized_lines.append(combined)
        if continuation:
            normalized_lines.append(continuation)

        # Extract shell variable assignments
        for line in normalized_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Check for variable assignment before any comment
            code_part = stripped.split("#", 1)[0].strip()
            match = _SHELL_VAR_ASSIGN_RE.match(code_part)
            if match:
                var_name = match.group(1)
                raw_val = match.group(2)
                # Unquote if enclosed in quotes
                if (raw_val.startswith('"') and raw_val.endswith('"')) or (
                    raw_val.startswith("'") and raw_val.endswith("'")
                ):
                    val = raw_val[1:-1]
                else:
                    val = raw_val
                # Expand variables
                expanded_val = _expand_shell_vars(val, variables)
                variables[var_name] = expanded_val

        # Locate rclone invocation
        rclone_command_line: str | None = None
        for line in normalized_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if re.search(r"\brclone\s+(bisync|sync)\b", stripped):
                rclone_command_line = stripped
                break

        if not rclone_command_line:
            raise ScriptImportError("No 'rclone bisync' or 'rclone sync' command found in script.")

        # Tokenize the rclone command line with shlex
        expanded_command = _expand_shell_vars(rclone_command_line, variables)
        try:
            tokens = shlex.split(expanded_command, comments=True)
        except ValueError as err:
            raise ScriptImportError(f"Failed to tokenize script command: {err}") from err

        # Find where 'rclone' starts
        try:
            rclone_idx = next(i for i, token in enumerate(tokens) if token == "rclone")
        except StopIteration:
            raise ScriptImportError("Could not locate 'rclone' executable token.") from None

        subcommand_idx = rclone_idx + 1
        if subcommand_idx >= len(tokens):
            raise ScriptImportError("rclone invocation is missing a subcommand (bisync/sync).")

        subcommand = tokens[subcommand_idx]
        if subcommand not in ("bisync", "sync"):
            raise ScriptImportError(
                f"Unsupported rclone subcommand: '{subcommand}'. "
                "Only bisync and sync are supported."
            )

        direction = SyncDirection.BIDIRECTIONAL if subcommand == "bisync" else SyncDirection.A_TO_B

        args = tokens[subcommand_idx + 1 :]
        positional_args: list[str] = []
        excludes: list[str] = []
        includes: list[str] = []
        conflict_policy = ConflictPolicy.KEEP_BOTH
        max_delete_files = 25
        check_access = False
        bandwidth_limit: str | None = None
        transfers: int | None = None
        extra_flags: list[str] = []

        i = 0
        while i < len(args):
            token = args[i]
            if token.startswith("-"):
                # Handle flags
                if token in ("--exclude", "--filter", "--include"):
                    if i + 1 < len(args):
                        pattern = args[i + 1]
                        if token == "--include":
                            includes.append(pattern)
                        else:
                            excludes.append(pattern)
                        i += 2
                        continue
                    i += 1
                    continue

                if token == "--conflict-resolve":
                    if i + 1 < len(args):
                        res_val = args[i + 1].lower()
                        if res_val in ("none", "keep_both"):
                            conflict_policy = ConflictPolicy.KEEP_BOTH
                        elif res_val == "newer":
                            conflict_policy = ConflictPolicy.NEWER
                        elif res_val == "larger":
                            conflict_policy = ConflictPolicy.LARGER
                        elif res_val == "path1":
                            conflict_policy = ConflictPolicy.PATH1
                        elif res_val == "path2":
                            conflict_policy = ConflictPolicy.PATH2
                        i += 2
                        continue
                    i += 1
                    continue

                if token == "--max-delete":
                    if i + 1 < len(args):
                        try:
                            # Might be "50%" or "25"
                            val_str = args[i + 1].rstrip("%")
                            max_delete_files = int(val_str)
                        except ValueError:
                            pass
                        i += 2
                        continue
                    i += 1
                    continue

                if token == "--check-access":
                    check_access = True
                    i += 1
                    continue

                if token == "--bwlimit":
                    if i + 1 < len(args):
                        bandwidth_limit = args[i + 1]
                        i += 2
                        continue
                    i += 1
                    continue

                if token == "--transfers":
                    if i + 1 < len(args):
                        with contextlib.suppress(ValueError):
                            transfers = int(args[i + 1])
                        i += 2
                        continue
                    i += 1
                    continue

                # Filter out managed flags
                flag_base = token.split("=")[0]
                if flag_base not in _MANAGED_FLAGS and not token.startswith("$"):
                    extra_flags.append(token)
                i += 1
            else:
                # Positional argument (side A or side B or trailing flag variable)
                if not token.startswith("$"):
                    positional_args.append(token)
                i += 1

        if len(positional_args) < 2:
            raise ScriptImportError(
                f"rclone {subcommand} requires two paths (side A and side B), "
                f"found {len(positional_args)}."
            )

        side_a_str = positional_args[0]
        side_b_str = positional_args[1]

        side_a = _parse_endpoint_spec(side_a_str)
        side_b = _parse_endpoint_spec(side_b_str)

        # Derive suggested profile name
        # Priority: explicit default_name -> name from side_b -> name from side_a -> "sync"
        suggested_name = ""
        if default_name and default_name.strip() and default_name.strip() != "sync":
            suggested_name = default_name.strip()
        else:
            if side_b.path.strip():
                suggested_name = Path(side_b.path).name
            elif side_a.path.strip():
                suggested_name = Path(side_a.path).name
            if not suggested_name:
                suggested_name = default_name or "sync"

        options = SyncOptions(
            direction=direction,
            conflict_policy=conflict_policy,
            max_delete_files=max_delete_files,
            check_access=check_access,
            excludes=tuple(excludes),
            includes=tuple(includes),
            bandwidth_limit=bandwidth_limit,
            transfers=transfers,
            extra_flags=tuple(extra_flags),
        )

        return SyncProfile(
            name=suggested_name,
            side_a=side_a,
            side_b=side_b,
            options=options,
        )


class ProfileTransfer:
    """Export and import sync profiles without sensitive credentials."""

    SCHEMA_VERSION = 1

    @classmethod
    def profile_to_dict(cls, profile: SyncProfile) -> dict[str, Any]:
        """Convert a single profile to an exportable dictionary."""
        return {
            "name": profile.name,
            "side_a": profile.side_a.to_dict(),
            "side_b": profile.side_b.to_dict(),
            "options": profile.options.to_dict(),
            "schedule": profile.schedule.to_dict(),
        }

    @classmethod
    def export_to_dict(cls, profiles: list[SyncProfile] | SyncProfile) -> dict[str, Any]:
        """Convert profiles to an envelope dict with schema metadata."""
        if isinstance(profiles, SyncProfile):
            profiles = [profiles]
        return {
            "version": cls.SCHEMA_VERSION,
            "generator": "pontis",
            "profiles": [cls.profile_to_dict(p) for p in profiles],
        }

    @classmethod
    def export_to_json(cls, profiles: list[SyncProfile] | SyncProfile, indent: int = 2) -> str:
        """Export profiles to a formatted JSON string."""
        data = cls.export_to_dict(profiles)
        return json.dumps(data, indent=indent, ensure_ascii=False)

    @classmethod
    def export_to_file(cls, profiles: list[SyncProfile] | SyncProfile, path: Path | str) -> None:
        """Export profiles to a JSON file."""
        target = Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(cls.export_to_json(profiles), encoding="utf-8")
        except Exception as err:
            raise ProfileExportError(f"Failed to export profiles to '{target}': {err}") from err

    @classmethod
    def profile_from_dict(cls, data: dict[str, Any]) -> SyncProfile:
        """Deserialize a single profile from a dictionary."""
        try:
            name = str(data["name"])
            side_a = Endpoint.from_dict(data["side_a"])
            side_b = Endpoint.from_dict(data["side_b"])
            options = SyncOptions.from_dict(data.get("options", {}))
            schedule = Schedule.from_dict(data.get("schedule", {}))
            return SyncProfile(
                name=name,
                side_a=side_a,
                side_b=side_b,
                options=options,
                schedule=schedule,
            )
        except KeyError as err:
            raise ProfileImportError(f"Missing required profile field: {err}") from err
        except Exception as err:
            raise ProfileImportError(f"Invalid profile structure: {err}") from err

    @classmethod
    def import_from_dict(cls, data: dict[str, Any]) -> list[SyncProfile]:
        """Deserialize a list of profiles from an envelope dict or raw profile list."""
        if "profiles" in data and isinstance(data["profiles"], list):
            profiles_list = data["profiles"]
        elif "name" in data and "side_a" in data and "side_b" in data:
            profiles_list = [data]
        else:
            raise ProfileImportError("Invalid data format: expected 'profiles' list.")

        results: list[SyncProfile] = []
        for item in profiles_list:
            if not isinstance(item, dict):
                raise ProfileImportError("Each profile entry must be a dictionary.")
            results.append(cls.profile_from_dict(item))
        return results

    @classmethod
    def import_from_json(cls, json_str: str) -> list[SyncProfile]:
        """Parse a JSON string into a list of :class:`SyncProfile` instances."""
        try:
            data = json.loads(json_str)
        except Exception as err:
            raise ProfileImportError(f"Invalid JSON format: {err}") from err

        if isinstance(data, list):
            # Direct list of profile dicts
            return [cls.profile_from_dict(item) for item in data]
        if isinstance(data, dict):
            return cls.import_from_dict(data)
        raise ProfileImportError("JSON root must be an object or a list.")

    @classmethod
    def import_from_file(cls, path: Path | str) -> list[SyncProfile]:
        """Read a JSON file and return the list of parsed profiles."""
        file_path = Path(path)
        if not file_path.is_file():
            raise ProfileImportError(f"File not found: {file_path}")
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as err:
            raise ProfileImportError(f"Failed to read file '{file_path}': {err}") from err
        return cls.import_from_json(content)
