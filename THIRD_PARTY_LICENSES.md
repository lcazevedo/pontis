# Third-Party Licenses

Pontis itself is licensed under the **GNU General Public License v3.0 or later (`GPL-3.0-or-later`)**. See [LICENSE](LICENSE).

All runtime and development dependencies used by Pontis are open-source and compatible with `GPL-3.0-or-later`.

## Runtime Dependencies

| Component | Version (dev env) | License | Source / Upstream |
|---|---|---|---|
| **PySide6** (`PySide6-Essentials`, `PySide6-Addons`, `shiboken6`) | `6.12.0` (requires `>=6.6`) | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` | <https://doc.qt.io/qtforpython-6/> |
| **platformdirs** | `4.14.0` (requires `>=4.0`) | `MIT` | <https://github.com/tox-dev/platformdirs> |
| **keyring** | `25.7.0` (requires `>=24.0`) | `MIT` | <https://github.com/jaraco/keyring> |
| **watchdog** | `7.0.0` (requires `>=4.0`) | `Apache-2.0` | <https://github.com/gorakhargosh/watchdog> |

## External System Engine (Not Bundled in v1)

| Component | Minimum Version | License | Source / Upstream |
|---|---|---|---|
| **rclone** | `1.66.0` | `MIT` | <https://rclone.org> |

> In Pontis v1 (Linux), `rclone` is detected from the user's configured path, application data bin directory, or system `PATH` and invoked as an external subprocess. It is not bundled inside the repository or Python package.

## Development & QA Tools

| Component | Version (dev env) | License | Source / Upstream |
|---|---|---|---|
| **ruff** | `0.17.3` (requires `>=0.5`) | `MIT` | <https://github.com/astral-sh/ruff> |
| **mypy** | `2.4.1` (requires `>=1.10`) | `MIT` | <https://github.com/python/mypy> |
| **pytest** | `9.2.0` (requires `>=8.0`) | `MIT` | <https://github.com/pytest-dev/pytest> |
| **pytest-qt** | `4.5.0` (requires `>=4.4`) | `MIT` | <https://github.com/pytest-dev/pytest-qt> |
| **pre-commit** | `>=3.7` | `MIT` | <https://github.com/pre-commit/pre-commit> |

## Compatibility Note

- **MIT** and **Apache-2.0** are compatible with **GPL-3.0-or-later**.
- **PySide6** (`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`) is compatible with **GPL-3.0-or-later**.
