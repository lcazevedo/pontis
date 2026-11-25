# Security Policy

## Supported Versions

Pontis is currently approaching its initial `1.0` Linux release. Security fixes
are applied to the `main` branch and included in the latest tagged release.

| Version | Supported |
|---|---|
| `main` / latest release | Yes |
| Older pre-release snapshots | No |

## Reporting a Vulnerability

Please **do not** report security vulnerabilities through public GitHub issues.

Instead, report them privately using GitHub Security Advisories:

- <https://github.com/lcazevedo/pontis/security/advisories/new>

When reporting an issue, please include:

1. A clear description of the vulnerability and its potential impact.
2. Steps to reproduce (or a minimal proof of concept).
3. Your Pontis version, Linux distribution, Python version, and `rclone` version.

We aim to acknowledge reports within **5 business days** and coordinate a fix
and disclosure timeline once the issue is confirmed.

## Security Design & Guardrails

Pontis handles user files and cloud credentials. Its design enforces the
following boundaries:

- **Isolated `rclone.conf`:** Pontis stores cloud remotes in its own
  application configuration file (`~/.config/pontis/rclone.conf`, permission
  `0600`) passed explicitly via `--config`, never modifying the user's
  `~/.config/rclone/rclone.conf`.
- **System Keyring for Passwords:** Optional encryption passwords for
  `rclone.conf` are stored in the OS keyring (`keyring`) and injected via
  `RCLONE_CONFIG_PASS` rather than saved in plain text in SQLite or JSON.
- **No Credentials in Exports:** Exported JSON profiles exclude OAuth tokens,
  passwords, and secrets.
- **Managed Flag Protection:** `RcloneAdapter` blocks user-supplied
  `extra_flags` that override safety-critical flags (`--resync`, `--force`,
  `--config`, `--workdir`, `--max-delete`, `--dry-run`, `--use-json-log`, etc.).
- **Data-Loss Guardrails for `bisync`:**
  - First real runs require a prior successful `--dry-run` simulation.
  - Failed `bisync` runs **never** trigger `--resync` automatically.
  - Mass deletions above the configured file-count threshold (default: `25`)
    require explicit user review and confirmation.
- **Minimal Update Checks:** Release checks only perform read-only HTTPS GET
  requests to the GitHub Releases API (no telemetry, no analytics, no tracking).
