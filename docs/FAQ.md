# Frequently Asked Questions (FAQ)

> 🌐 **Language:** **English** | [Português (Brasil)](FAQ.pt-BR.md)

### Why does Pontis use `rclone` instead of `rsync`?
`rsync` works great over local disks and SSH/SFTP, but it does not support cloud APIs like Google Drive, OneDrive, or Dropbox natively, and it is primarily one-way. `rclone` supports 70+ cloud storage providers and includes `bisync` for stateful two-way synchronization.

### Why is `--dry-run` required on the first execution of a profile?
`rclone bisync` needs an initial baseline listing (`--resync`) when no prior state exists. Running a mandatory `--dry-run` first lets you verify both paths, filters, and planned actions before any file is copied or modified.

### Why does Pontis refuse to run `--resync` automatically after a failure?
If `bisync` fails mid-run because a folder was temporarily unavailable, unmounted, or corrupted, running `--resync` blindly could propagate empty states or duplicate/overwrite files. Pontis stops safely, reports the error in the UI and history log, and asks for your explicit confirmation before running `--resync`.

### How does the 25-file deletion limit work?
By default, Pontis sets `max_delete_files = 25` in `SyncOptions`. Small, everyday operations (like renaming a few files or deleting under the limit) run smoothly without false alarms. If more than 25 deletions are detected in one run, Pontis triggers its **Safety Protection** check and asks you to review the list before authorizing deletion. You can adjust this threshold per profile in **Advanced Options**.

### Why are native Google Docs / Sheets / Slides skipped?
Google Workspace native documents (`.gdoc`, `.gsheet`, `.gslides`) have no fixed byte size or standard checksum on Google Drive, which frequently triggers errors or false mismatches in `rclone bisync`. Pontis enables `--drive-skip-gdocs` by default on Google Drive profiles to keep synchronization reliable.

### Where does Pontis store its database, config, and logs?
Pontis uses standard XDG directories via `platformdirs`:
- **Configuration** (`rclone.conf`, `settings.json`): `~/.config/pontis/`
- **Data & SQLite database** (`pontis.db`, `bisync/<profile_id>/`, `locks/`): `~/.local/share/pontis/`
- **Rotating run logs** (`runs/run_<id>.log`): `~/.local/state/pontis/log/` (or `$XDG_STATE_HOME` / `user_log_path`)

Your personal `~/.config/rclone/rclone.conf` is never modified.

### Why doesn't v1 include automatic scheduled syncing?
Background scheduling requires OS-specific daemon/tray lifecycle integration (`systemd --user` timers, catch-up policies, battery/metered network checks). v1 focuses on rock-solid manual sync, while already preparing the database schema (`schedule` column), `SchedulerBackend` protocol, and headless CLI (`pontis run <profile>`). If you need scheduled runs today on Linux, you can call `pontis run <profile>` from a `systemd --user` timer or `cron`.

### Will Pontis support Windows or macOS?
v1 targets Linux only, while the codebase uses `pathlib`, `platformdirs`, `PySide6`, and `keyring` so Windows and macOS support can be added in future versions.

### Does Pontis collect telemetry or send data anywhere?
No. Pontis has zero telemetry, ads, or analytics. The only network connections it makes (besides `rclone` talking to your configured cloud remotes) are optional read-only HTTPS GET checks to GitHub Releases when update checking is enabled—which you can turn off in **Preferences**.

### How can I support Pontis?
Pontis is free and open-source (`GPL-3.0-or-later`). Contributions (bug reports, docs, translations, PRs) are always appreciated. Optional voluntary donations are available via [GitHub Sponsors](https://github.com/sponsors/lcazevedo) and [Ko-fi](https://ko-fi.com/lcazevedo).
