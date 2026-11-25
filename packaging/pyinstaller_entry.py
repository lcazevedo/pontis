# SPDX-License-Identifier: GPL-3.0-or-later
"""PyInstaller entry point for Pontis."""

from __future__ import annotations

from pontis.app import main

if __name__ == "__main__":
    raise SystemExit(main())
