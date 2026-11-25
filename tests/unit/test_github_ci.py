# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests validating GitHub Actions workflows, issue/PR templates, and funding config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

ROOT_DIR = Path(__file__).resolve().parents[2]
GITHUB_DIR = ROOT_DIR / ".github"


def _load_yaml(path: Path) -> dict[Any, Any]:
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"Expected mapping in {path}"
    return data


def test_ci_workflow_structure() -> None:
    """CI workflow defines quality, tests, and AppImage build jobs."""
    ci = _load_yaml(GITHUB_DIR / "workflows" / "ci.yml")
    assert ci["name"] == "CI"
    jobs = ci["jobs"]
    assert set(jobs.keys()) == {"quality", "tests", "build-appimage"}
    assert jobs["quality"]["runs-on"] == "ubuntu-24.04"
    assert jobs["tests"]["runs-on"] == "ubuntu-24.04"
    assert jobs["build-appimage"]["runs-on"] == "ubuntu-22.04"
    assert jobs["build-appimage"]["needs"] == ["quality", "tests"]


def test_release_workflow_structure() -> None:
    """Release workflow triggers on v* tags and verifies before publishing."""
    rel = _load_yaml(GITHUB_DIR / "workflows" / "release.yml")
    assert rel["name"] == "Release"
    # PyYAML parses top-level `on` key as boolean True under YAML 1.1
    triggers = rel.get("on") or rel.get(True)
    assert isinstance(triggers, dict)
    assert "v*" in triggers["push"]["tags"]
    jobs = rel["jobs"]
    assert set(jobs.keys()) == {"verify", "build-and-release"}
    assert jobs["build-and-release"]["needs"] == "verify"


def test_funding_and_dependabot_yaml() -> None:
    """FUNDING.yml keeps only GitHub Sponsors and Ko-fi; Dependabot tracks actions."""
    funding = _load_yaml(GITHUB_DIR / "FUNDING.yml")
    assert funding["github"] == ["lcazevedo"]
    assert funding["ko_fi"] == "lcazevedo"
    assert "buy_me_a_coffee" not in funding

    dependabot = _load_yaml(GITHUB_DIR / "dependabot.yml")
    assert dependabot["version"] == 2
    assert dependabot["updates"][0]["package-ecosystem"] == "github-actions"


def test_issue_pr_templates_and_setup_guide() -> None:
    """Issue forms, PR template, and GitHub setup guide exist and are valid."""
    tpl_dir = GITHUB_DIR / "ISSUE_TEMPLATE"
    config = _load_yaml(tpl_dir / "config.yml")
    assert config["blank_issues_enabled"] is False
    assert len(config["contact_links"]) >= 2

    bug = _load_yaml(tpl_dir / "bug_report.yml")
    assert "bug" in bug["labels"]
    assert len(bug["body"]) >= 5

    feat = _load_yaml(tpl_dir / "feature_request.yml")
    assert "enhancement" in feat["labels"]
    assert len(feat["body"]) >= 3

    pr_tpl = (GITHUB_DIR / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    assert "GPL-3.0-or-later" in pr_tpl
    assert "pytest" in pr_tpl

    setup_guide = (ROOT_DIR / "docs" / "GITHUB_SETUP.md").read_text(encoding="utf-8")
    assert "Quality (ruff & mypy)" in setup_guide
    assert "Tests (pytest)" in setup_guide
    assert "Build AppImage (Linux x86_64)" in setup_guide
