# Architecture Decision Records (ADRs)

This directory records the major architectural and product decisions made during the design and implementation of **Pontis**.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-rclone-as-sync-engine.md) | Use rclone (`bisync`) as the Sync Engine | Accepted |
| [0002](0002-pyside6-and-layered-architecture.md) | PySide6 GUI and Layered Architecture | Accepted |
| [0003](0003-sqlite-and-platformdirs.md) | SQLite Persistence with `platformdirs` | Accepted |
| [0004](0004-isolated-rclone-config-and-keyring.md) | Isolated `rclone.conf` and System Keyring for Secrets | Accepted |
| [0005](0005-bisync-safety-guardrails.md) | Safety Guardrails for `rclone bisync` | Accepted |
| [0006](0006-manual-sync-v1-and-scheduler-extension.md) | Manual Sync in v1 with Scheduler Extension Points | Accepted |
