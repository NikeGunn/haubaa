"""Tests for Skill Matcher — task-to-skill matching."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.skills.loader import SkillLoader
from hauba.skills.matcher import SkillMatcher


@pytest.fixture
def loader(tmp_path: Path) -> SkillLoader:
    """Create a loader with two skills."""
    (tmp_path / "code-gen.md").write_text(
        "# Skill: code-generation\n"
        "## Capabilities\n"
        "- Generate Python code\n"
        "- Build REST APIs\n"
        "## When To Use\n"
        "- User requests code creation\n"
    )
    (tmp_path / "deploy.md").write_text(
        "# Skill: deployment\n"
        "## Capabilities\n"
        "- Deploy to cloud platforms\n"
        "- Configure CI/CD pipelines\n"
        "## When To Use\n"
        "- User wants to deploy an application\n"
    )
    return SkillLoader(skill_dirs=[tmp_path])


def test_match_returns_results(loader: SkillLoader) -> None:
    matcher = SkillMatcher(loader)
    matches = matcher.match("build a Python REST API")
    assert len(matches) > 0
    assert matches[0].score > 0


def test_best_match(loader: SkillLoader) -> None:
    matcher = SkillMatcher(loader)
    match = matcher.best_match("deploy my application to cloud")
    assert match is not None
    assert match.skill.name == "deployment"


def test_no_match(loader: SkillLoader) -> None:
    matcher = SkillMatcher(loader)
    match = matcher.best_match("xyz quantum entanglement")
    assert match is None


def test_compose_skills(loader: SkillLoader) -> None:
    matcher = SkillMatcher(loader)
    combined = matcher.compose_skills(["code-generation", "deployment"])
    assert "code-generation" in combined
    assert "deployment" in combined
    assert "Capabilities" in combined
