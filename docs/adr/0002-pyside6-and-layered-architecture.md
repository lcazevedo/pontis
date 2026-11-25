# ADR 0002: PySide6 GUI and Layered Architecture

- **Status:** Accepted
- **Date:** 2026-10-30

## Context

Pontis needs a responsive, cross-platform desktop UI with native look-and-feel, Light/Dark themes, runtime language switching (`pt_BR` and `en`), and clean separation between business rules, process execution, and presentation.

## Decision

1. **GUI Toolkit:** Use **PySide6** (Qt 6 official Python bindings, LGPL-3.0). PyQt6 is excluded due to GPL/commercial licensing constraints on contributors and future packaging.
2. **Strict Layering under `src/pontis/`:**
   - `domain/`: Pure Python dataclasses and enums (`SyncProfile`, `Endpoint`, `SyncOptions`, `Schedule`, `RunResult`). Zero Qt or I/O imports.
   - `services/`: Application workflows (`ProfileService`, `RunService`, `RemoteService`, `ConflictService`, `WatchService`, `UpdateService`, import/export).
   - `infra/`: Subprocess execution (`RcloneAdapter`), SQLite persistence, keyring, `flock` locks, settings, and rotating run logs.
   - `ui/`: PySide6 windows, wizards, dialogs, and QThread workers. UI components never invoke `rclone` directly; all operations flow through services.

## Consequences

- **Positive:** Core logic and `RcloneAdapter` can be unit- and integration-tested headlessly without starting Qt; the CLI (`pontis.cli`) and GUI share the exact same services.
- **Negative:** Slightly more boilerplate across layers, which pays off in testability and maintainability.
