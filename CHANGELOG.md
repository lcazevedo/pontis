# Changelog

All notable changes to **Pontis** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Project Foundation & Architecture:**
  - Python 3.12 package layout (`src/pontis/`) licensed under `GPL-3.0-or-later` with SPDX headers across all source files.
  - Pure domain models (`SyncProfile`, `Endpoint`, `SyncOptions`, `Schedule`, `RunResult`) and `SchedulerBackend` extension protocol.
  - Versioned SQLite persistence via `sqlite3` (`PRAGMA user_version` migrations) and XDG paths via `platformdirs`.
- **rclone Sync Engine & CLI:**
  - Hybrid `rclone` locator (configured path, app bin directory, or `PATH`) enforcing minimum version `1.66.0`.
  - `RcloneAdapter` supporting `rclone bisync` (default) and one-way `rclone sync`, `--use-json-log` parsing, `--workdir` isolation per profile, `flock` per-profile locking, and `FORBIDDEN_EXTRA_FLAGS` protection.
  - First-run safety gate requiring a successful `--dry-run` before the first real sync, and explicit confirmation without automatic `--resync` after failures.
  - CLI subcommands: `pontis profile add|list|remove|export|import|import-script`, `pontis remote add|list|test|remove|import|password`, `pontis run`, and `pontis watch`.
- **Cloud Remotes Management:**
  - `RemoteService` managing an isolated `~/.config/pontis/rclone.conf` (`0600`), OAuth creation, connectivity tests, external `rclone.conf` import, and encrypted config password storage via system `keyring`.
- **Desktop GUI (PySide6):**
  - Main window with profiles table, empty state, Light/Dark/System themes, and live status indicators.
  - Step-by-step Profile Wizard (`QWizard`) with local and cloud directory browser (`rclone lsf --dirs-only`).
  - Advanced Options dialog (`--include`/`--exclude` filters, conflict policy, mass-deletion threshold, `--check-access`, `--bwlimit`, `--transfers`, free flags validator, and live shell command preview).
  - Asynchronous sync execution (`SyncWorker`), real-time `SyncProgressDialog`, `DryRunSummaryDialog`, and friendly mass-deletion safety confirmation (default threshold: 25 files).
  - Execution history viewer (`HistoryDialog`) with rotating run logs (`RunLogManager`), log export, and manual `--resync` recovery prompt.
  - Interactive `ConflictResolutionDialog` for `*.conflict1`/`*.conflict2` files on local and cloud endpoints.
  - Shell script importer (`sync.sh`), credential-free JSON profile import/export, and on-demand `watchdog` real-time folder watcher (`WatchDialog`).
  - Complete English (`en`) and Brazilian Portuguese (`pt_BR`) i18n catalog with live runtime language switching, persistent `settings.json`, `PreferencesDialog`, GitHub Releases update checker, keyboard shortcuts, and accessible high-contrast focus styles.
- **Documentation & Voluntary Support:**
  - Bilingual documentation (`README.md`, `README.pt-BR.md`, user guides, Google `client_id` setup guide, FAQ, ADRs, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `THIRD_PARTY_LICENSES.md`).
  - Application screenshots generated with fictional profiles in `docs/screenshots/`.
  - `.github/FUNDING.yml` and discreet, non-intrusive voluntary support links (GitHub Sponsors, Ko-fi, Buy Me a Coffee) in the status bar, Help menu, and About dialog.
