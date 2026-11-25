# SPDX-License-Identifier: GPL-3.0-or-later
"""Central repository, documentation, and voluntary support links for Pontis."""

from __future__ import annotations

GITHUB_REPO = "lcazevedo/pontis"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
GITHUB_ISSUES_URL = f"{GITHUB_URL}/issues"
GITHUB_SECURITY_URL = f"{GITHUB_URL}/security/advisories/new"

GITHUB_SPONSORS_URL = "https://github.com/sponsors/lcazevedo"
KOFI_URL = "https://ko-fi.com/lcazevedo"
BUYMEACOFFEE_URL = "https://buymeacoffee.com/lcazevedo"

SUPPORT_LINKS: tuple[tuple[str, str], ...] = (
    ("ui.support.github_sponsors", GITHUB_SPONSORS_URL),
    ("ui.support.kofi", KOFI_URL),
    ("ui.support.buymeacoffee", BUYMEACOFFEE_URL),
)
