# ADR 0006: Manual Sync in v1 with Scheduler Extension Points

- **Status:** Accepted
- **Date:** 2026-10-30

## Context

Background scheduled synchronization requires OS-specific daemon/tray lifecycles (`systemd --user` timers on Linux, Task Scheduler on Windows, `launchd` on macOS), network/battery awareness, and catch-up policies. Implementing and verifying that across environments would delay a stable manual v1.

## Decision

- **v1 scope is strictly manual synchronization** (GUI button, CLI `pontis run`, or on-demand `pontis watch` session).
- Prepare clean extension points from day one without exposing incomplete scheduling features:
  - `Schedule` model (`ScheduleKind.MANUAL`) and `schedule` JSON column in SQLite `profiles` table.
  - `SchedulerBackend` protocol in `src/pontis/infra/scheduler_backend.py`.
  - Headless CLI entry point `pontis run <profile>` decoupled from the GUI.
  - Disabled/placeholder scheduling note in the Profile Wizard summary/conflict step.

## Consequences

- **Positive:** Delivers a solid, well-tested v1 focused on safety and usability while keeping the database schema and service boundaries ready for background scheduling in v2.
- **Negative:** Users who want unattended periodic runs in v1 must invoke `pontis run <profile>` from their own cron or `systemd --user` timer.
