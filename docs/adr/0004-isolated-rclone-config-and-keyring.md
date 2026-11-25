# ADR 0004: Isolated `rclone.conf` and System Keyring for Secrets

- **Status:** Accepted
- **Date:** 2026-11-01

## Context

Many users already have an existing `~/.config/rclone/rclone.conf` managed manually or by other scripts. Modifying that file directly from a GUI app risks breaking existing user workflows or unintentionally altering permissions and remotes. Additionally, OAuth tokens and config encryption passwords must never be stored in SQLite or exported profile JSON files.

## Decision

- Maintain an **isolated** configuration file at `~/.config/pontis/rclone.conf` (enforced permission `0600`) passed explicitly via `--config` to every `rclone` invocation.
- Provide explicit import workflows (`pontis remote import`) so users can copy remotes from `~/.config/rclone/rclone.conf` or any custom config file into Pontis without mutating the source file.
- Store optional `rclone.conf` encryption passwords in the OS secret service via **`keyring`** and inject them via the `RCLONE_CONFIG_PASS` environment variable at execution time.
- Strip all credentials and tokens from profile JSON exports (`ProfileTransfer`).

## Consequences

- **Positive:** Complete isolation from the user's personal `rclone.conf`, safe profile sharing, and secure handling of encrypted rclone configurations.
- **Negative:** Users who add a remote via standalone `rclone config` outside Pontis must import it into Pontis (or pass `--rclone-config` in CLI mode).
