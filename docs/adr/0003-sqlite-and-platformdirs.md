# ADR 0003: SQLite Persistence with `platformdirs`

- **Status:** Accepted
- **Date:** 2026-10-31

## Context

Pontis must persist synchronization profiles, execution history (`RunResult`), rotating log pointers, and application configuration using standard XDG directories on Linux while remaining portable to Windows and macOS in future releases.

## Decision

- Use Python's standard library **`sqlite3`** with explicit, append-only SQL migrations tracked via `PRAGMA user_version` (`MIGRATIONS` list in `src/pontis/infra/database.py`).
- Resolve all data, config, and log directories through **`platformdirs`** (`user_data_path`, `user_config_path`, `user_log_path`).
- Enable SQLite `WAL` mode and `check_same_thread=False` on dedicated background worker connections so UI progress dialogs can execute `RunService` in a `QThread` safely.
- Store lightweight UI preferences (`language`, `theme`, `rclone_path`, update flags) in an atomic JSON file (`~/.config/pontis/settings.json`).

## Consequences

- **Positive:** Zero external database server dependencies, transactional integrity, cascade deletion of run history, and clean XDG directory compliance (`~/.local/share/pontis`, `~/.config/pontis`, `~/.local/state/pontis/log`).
- **Negative:** Schema changes must always be added as new entries in `MIGRATIONS` without editing released migrations.
