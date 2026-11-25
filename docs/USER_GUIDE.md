# Pontis User Guide

> 🌐 **Language:** **English** | [Português (Brasil)](USER_GUIDE.pt-BR.md)

This guide walks through day-to-day usage of **Pontis** on Linux, from connecting cloud storage accounts to handling conflicts, logs, and CLI automation.

---

## 1. Managing Cloud Accounts (Remotes)

Pontis keeps its own isolated rclone configuration at `~/.config/pontis/rclone.conf` (with `0600` file permissions) so your existing `~/.config/rclone/rclone.conf` is never modified.

### Import an existing `rclone.conf`

If you already configured remotes with `rclone config`:

```bash
pontis remote import
```

You can also import a single remote or specify an encrypted source config:

```bash
pontis remote import --remote gdrive
pontis remote import --from /path/to/rclone.conf --overwrite
```

### Add a new cloud remote

Use `pontis remote add <name> <type>`:

```bash
# Interactive OAuth in your browser (Google Drive example)
pontis remote add gdrive drive

# Recommended: pass your own Google client_id and client_secret
pontis remote add gdrive drive \
  --param client_id=YOUR_ID.apps.googleusercontent.com \
  --param client_secret=YOUR_SECRET
```

See [Google Client ID Guide](GOOGLE_CLIENT_ID.md) for creating free Google Drive OAuth credentials.

### Test, list, remove, and password protection

```bash
pontis remote list
pontis remote test gdrive
pontis remote remove gdrive

# Optional: store your rclone.conf encryption password in the system keyring
pontis remote password set
pontis remote password status
pontis remote password remove
```

---

## 2. Creating and Editing Profiles

Open `pontis` and click **New Profile** (`Ctrl+N`), or edit an existing profile (`Ctrl+E` or double-click).

The **Profile Wizard** guides you through:

1. **Name:** Unique profile name.
2. **Side A:** Local folder or cloud remote + folder (with interactive folder browser).
3. **Side B:** Local folder or cloud remote + folder.
4. **Direction:**
   - **Bidirectional (`↔`):** Uses `rclone bisync` (default).
   - **A → B (`→`):** One-way `rclone sync` from Side A to Side B.
   - **B → A (`←`):** One-way `rclone sync` from Side B to Side A.
5. **Conflict Policy:**
   - **Keep both (`keep_both`, default & safest):** Keeps both copies as `*.conflict1` / `*.conflict2` (preserving extensions) so you can review them later.
   - **Keep newer (`newer`)**, **Keep larger (`larger`)**, **Side A wins (`path1`)**, or **Side B wins (`path2`)**.
   - *(Note: Schedule options are disabled in v1; v1 runs manually on demand.)*
6. **Summary:** Review settings and optionally open **Advanced Options** before saving.

---

## 3. Advanced Options & Filters

Select a profile and press `Ctrl+Shift+O` (or click **Advanced Options**):

- **Filters:** Add `--include` and `--exclude` glob patterns (e.g. `*.tmp`, `node_modules/**`, `.git/**`).
- **Safety & Conflict:**
  - Change conflict policy.
  - Set the mass-deletion safety threshold (`max_delete_files`, default **25 files**).
  - Toggle `--check-access` (requires `RCLONE_TEST` marker files on both sides).
- **Performance & Network:**
  - Set bandwidth limit (`--bwlimit`, e.g., `5M`, `500K`).
  - Set parallel transfers (`--transfers`).
- **Extra Flags:** Add custom rclone flags. Safety-critical flags managed by Pontis (`--resync`, `--force`, `--config`, `--workdir`, `--max-delete`, `--dry-run`, `--use-json-log`, etc.) are blocked to prevent accidental misconfiguration.
- **Command Preview:** Inspect and copy the exact shell command Pontis will execute, toggling `--dry-run` and initial `--resync` preview modes.

---

## 4. Running a Synchronization Safely

### First Run (Mandatory Simulation)

The very first time you run a new profile, Pontis requires a successful `--dry-run` simulation before allowing real changes:

1. Select the profile and click **Sync Now** (`Ctrl+R`) or **Simulate (Dry Run)** (`Ctrl+Shift+R`).
2. Pontis runs `rclone` in simulation mode and displays a **Dry Run Summary** listing planned copies and deletions.
3. Confirm the summary to run the real initial sync (`--resync --resync-mode newer`, which copies missing files without deleting).

### Mass-Deletion Safety Protection

During normal runs, if `rclone bisync` detects more deletions than your configured threshold (default: **25 files**):

- Deletions **at or below** the threshold (such as normal file renames or small cleanups) proceed cleanly.
- Deletions **above** the threshold pause with a **Safety Protection** notice so you can review the affected files and explicitly authorize deletion if intended.

### Recovery After Interrupted `bisync` Errors

If a bidirectional run fails mid-way (for example, network drop or lock interruption), `rclone bisync` may require a manual `--resync`. **Pontis never runs `--resync` automatically after an error.** Instead, inspect the log in **History** (`Ctrl+H`) or trigger **Resync** manually from the progress/history dialog once you confirm both folders are in a healthy state.

---

## 5. Resolving Conflicts

When using the default `keep_both` policy and a file is edited on both sides between syncs, `rclone bisync` creates `*.conflict1` and `*.conflict2` files (preserving the original file extension).

1. Select the profile and click **Conflicts** (or use the prompt shown right after a sync detects conflicts).
2. Inspect text previews for Side A and Side B.
3. Choose an action per file or in batch:
   - **Keep Side A**
   - **Keep Side B**
   - **Keep Both (renamed)**
   - **Discard Both**
4. Apply changes and optionally run a follow-up sync.

---

## 6. History, Logs, Import/Export & Watchdog

- **History & Rotating Logs (`Ctrl+H`):** Filter past executions by profile or status (`success`, `error`, `cancelled`), read full logs, copy, or export logs to a file.
- **Import Shell Script (`File → Import Shell Script...`):** Parse an existing `sync.sh` script (extracting local/remote paths, direction, conflict mode, and `--exclude`/`--include` filters) directly into the Profile Wizard.
- **Export / Import Profiles (`JSON`):** Share or back up profile definitions via `File → Export Profile...` / `Import Profile...`. No OAuth tokens or passwords are ever exported.
- **Watch with Watchdog (`Ctrl+W`):** Watch local folder changes in real time during an active session, with configurable debounce before triggering `RunService`.

---

## 7. Preferences, Languages & Keyboard Shortcuts

Open **Preferences** (`Ctrl+,`) to configure:

- **Language:** Switch live between **Português (Brasil)** and **English**.
- **Theme:** System, Light, or Dark.
- **rclone Engine:** Set a custom `rclone` binary path, auto-detect, and test version compatibility (`>= 1.66.0`).
- **Updates:** Toggle startup check against GitHub Releases (read-only check; can be disabled completely).

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+R` | Sync Now |
| `Ctrl+Shift+R` | Simulate (`--dry-run`) |
| `Ctrl+W` | Watch with Watchdog |
| `Ctrl+N` | New Profile |
| `Ctrl+E` | Edit Selected Profile |
| `Ctrl+Shift+O` | Advanced Options |
| `Ctrl+H` | History & Logs |
| `Delete` | Delete Profile |
| `F5` | Refresh Profiles |
| `Ctrl+,` | Preferences |
| `F1` | About Pontis |
| `Ctrl+Q` | Quit |
