# ADR 0005: Safety Guardrails for `rclone bisync`

- **Status:** Accepted
- **Date:** 2026-11-02

## Context

Bidirectional sync (`rclone bisync`) can cause irreversible data loss if invoked carelessly—especially on the first run, after interrupted runs, when large directory trees appear empty/deleted, or when conflicting changes occur on both sides simultaneously.

## Decision

Pontis enforces multiple non-negotiable guardrails around `bisync`:

1. **Per-profile `--workdir`:** Each profile keeps its `bisync` listing files under `<data_dir>/bisync/<profile_id>` so profiles never collide.
2. **Mandatory first `--dry-run`:** Before the first real execution of a profile (`needs_resync`), Pontis requires a successful `--dry-run` simulation and presents the planned copies/deletions for confirmation.
3. **Safe initial `--resync`:** Only when no prior `*.lst` state exists does Pontis pass `--resync --resync-mode newer` (never deleting files on initial sync).
4. **Never auto-retry `--resync` after failure:** If `bisync` fails mid-run and requests `--resync`, Pontis surfaces the error clearly and requires explicit manual confirmation before running `--resync`.
5. **Friendly mass-deletion protection:** Configured via an absolute file-count threshold (`max_delete_files`, default `25`). Deletions at or below the threshold proceed cleanly (auto-handling small normal renames/deletes via `--force`), while deletions above the threshold pause and present a clear review dialog before authorizing.
6. **Conservative conflict default & extension preservation:** Conflict policy defaults to `keep_both` (`--conflict-resolve none --suffix-keep-extension`), generating `*.conflict1` / `*.conflict2` files that can be resolved in `ConflictResolutionDialog`.
7. **Per-profile locking & flag allow/blocklist:** `flock` prevents concurrent runs of the same profile, and `FORBIDDEN_EXTRA_FLAGS` blocks user flags that could override safety parameters.
8. **Google Workspace docs safety:** `--drive-skip-gdocs` is enabled by default for Google Drive remotes to avoid hash/size mismatches on native Google Docs/Sheets/Slides.

## Consequences

- **Positive:** Dramatically reduces the risk of accidental mass deletion or silent data corruption.
- **Negative:** Adds one extra simulation step on a profile's very first run, which is deliberate and communicated clearly in the UI and documentation.
