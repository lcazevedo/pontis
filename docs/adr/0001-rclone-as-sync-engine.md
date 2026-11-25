# ADR 0001: Use rclone (`bisync`) as the Sync Engine

- **Status:** Accepted
- **Date:** 2026-10-30

## Context

Pontis aims to provide reliable bidirectional synchronization between local directories and cloud storage providers (Google Drive, OneDrive, Dropbox, S3, SFTP, WebDAV, etc.). Building custom protocol clients and sync state trackers for each provider would introduce massive maintenance overhead and risk subtle data corruption.

## Decision

Pontis delegates all file transfer and state diffing to **rclone** (`>= 1.66.0`), using `rclone bisync` as the default engine for bidirectional profiles and `rclone sync` for one-way profiles.

On Linux v1, Pontis uses a hybrid discovery strategy:
1. User-configured binary path (saved in `settings.json`).
2. Application-local binary (`<data_dir>/bin/rclone`), if present.
3. System `PATH`.

`rclone` is not bundled inside the repository or Python package in v1; users install it via their package manager or rclone's official installer.

## Consequences

- **Positive:** Instant support for 70+ cloud backends, battle-tested retries/checksumming, structured `--use-json-log` output, and clean MIT license compatibility.
- **Negative:** Users on Linux v1 must have `rclone >= 1.66.0` installed externally, and `rclone bisync` requires strict guardrails (see [ADR 0005](0005-bisync-safety-guardrails.md)).
- **Future:** Bundling `rclone` can be added as a packaging step later for Windows/macOS without changing the adapter interface.
