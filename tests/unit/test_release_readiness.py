# SPDX-License-Identifier: GPL-3.0-or-later
"""Release readiness checks for v1.0.0 metadata, SPDX headers, and documentation."""

from __future__ import annotations

import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pontis

ROOT_DIR = Path(__file__).resolve().parents[2]


def test_version_consistency_across_project() -> None:
    """pyproject.toml and pontis.__version__ match the stable 1.0.0 release."""
    pyproject = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    assert project["version"] == "1.0.0"
    assert pontis.__version__ == "1.0.0"
    assert "Development Status :: 5 - Production/Stable" in project["classifiers"]


def test_all_python_files_have_spdx_header() -> None:
    """Every Python source, test, script, and packaging file declares GPL-3.0-or-later SPDX."""
    missing: list[str] = []
    for folder in ("src", "tests", "scripts", "packaging"):
        for py_file in sorted((ROOT_DIR / folder).rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            lines = py_file.read_text(encoding="utf-8").splitlines()
            if not lines or "SPDX-License-Identifier: GPL-3.0-or-later" not in lines[0]:
                missing.append(str(py_file.relative_to(ROOT_DIR)))

    assert not missing, f"Python files missing SPDX header: {missing}"


def test_release_documents_and_metainfo() -> None:
    """Release docs, changelog, license files, and AppStream metadata are ready for 1.0.0."""
    for rel_path in (
        "LICENSE",
        "THIRD_PARTY_LICENSES.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "docs/RELEASE_ANNOUNCEMENT.md",
    ):
        path = ROOT_DIR / rel_path
        assert path.is_file() and path.stat().st_size > 0, f"Missing {rel_path}"

    changelog = (ROOT_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [1.0.0] - " in changelog

    metainfo = ROOT_DIR / "packaging" / "linux" / "io.github.lcazevedo.Pontis.metainfo.xml"
    root = ET.parse(metainfo).getroot()
    release_el = root.find("./releases/release")
    assert release_el is not None
    assert release_el.attrib.get("version") == "1.0.0"
