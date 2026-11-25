# Contributing to Pontis

Thank you for your interest in contributing to **Pontis**! Contributions of bug reports, documentation improvements, translations, and code are all welcome.

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development Environment

Pontis targets **Python 3.12** and uses **Conda** (`pontis-dev`) during development.

```bash
conda create -n pontis-dev python=3.12
conda activate pontis-dev
pip install -e ".[dev]"
pre-commit install
```

Make sure `rclone` (`>= 1.66.0`) is available in `PATH` if you plan to run integration or live sync tests.

## Running Checks & Tests

Run the full quality suite before opening a pull request:

```bash
QT_QPA_PLATFORM=offscreen pytest
ruff check .
mypy
```

- `QT_QPA_PLATFORM=offscreen` allows Qt UI tests to run headlessly.
- `mypy` runs in `strict = true` mode across `src/` and `tests/`.
- `ruff` enforces rules `E, F, W, I, B, UP, SIM` with a line length of `100`.

## Architecture & Code Conventions

Pontis follows a strict layered architecture under `src/pontis/`:

- `domain/`: Pure Python models (`SyncProfile`, `Endpoint`, `SyncOptions`, `Schedule`, `RunResult`). **No Qt and no I/O.**
- `services/`: Application orchestration (`ProfileService`, `RunService`, `RemoteService`, `ConflictService`, `WatchService`, `UpdateService`, import/export).
- `infra/`: External boundaries (`RcloneAdapter`, `rclone` detection, SQLite repositories and versioned migrations, `KeyringStore`, `SettingsManager`, `RunLogManager`, `flock` profile locks, `SchedulerBackend` protocol).
- `ui/`: PySide6 dialogs, main window, wizard, and widgets. **UI components must call services, never `rclone` directly.**
- `i18n/`: Translation catalog (`en` and `pt_BR`).

### Mandatory Rules for Code Changes

1. **SPDX License Header:** Every Python source file must start with:
   ```python
   # SPDX-License-Identifier: GPL-3.0-or-later
   ```
2. **Type Hints & Docstrings:** Add complete type hints to all new functions/classes and concise English docstrings.
3. **Internationalization (`i18n`):** Never hardcode user-facing UI strings. Add every new key to **both** `en` and `pt_BR` in `src/pontis/i18n/__init__.py` (verified automatically by `test_i18n_catalog_exact_parity`).
4. **Safety First in Tests:** Never run tests against real user folders (`~/Documents/...` or real cloud accounts). Always use `tmp_path`, temporary directories, and `--dry-run` first.
5. **Bisync Safety:** Never trigger `--resync` automatically after a failure, and never bypass `FORBIDDEN_EXTRA_FLAGS`.

## Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Keep pull requests focused on a single fix or feature.
3. Add or update automated tests covering your changes.
4. Ensure `pytest`, `ruff check .`, and `mypy` pass with zero errors.
5. Open a pull request describing the motivation, behavior changes, and how you tested them.
