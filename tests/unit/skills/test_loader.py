"""Tests for Skill Loader — .md file parsing and skill management."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.exceptions import SkillNotFoundError
from hauba.skills.loader import SkillLoader


@pytest.fixture
def skill_dir(tmp_path: Path) -> Path:
    """Create a temp directory with sample skill files."""
    skill = tmp_path / "code-gen.md"
    skill.write_text(
        "# Skill: code-generation\n"
        "## Capabilities\n"
        "- Generate Python code\n"
        "- Write unit tests\n"
        "## When To Use\n"
        "- User requests code creation\n"
        "- Bug fixing requires code changes\n"
        "## Approach\n"
        "1. Read existing codebase\n"
        "2. Plan implementation\n"
        "3. Write code with tests\n"
        "## Constraints\n"
        "- Must include type hints\n"
        "- Must include error handling\n"
    )
    return tmp_path


def test_load_skill_file(skill_dir: Path) -> None:
    loader = SkillLoader(skill_dirs=[skill_dir])
    skills = loader.load_all()

    assert "code-generation" in skills
    skill = skills["code-generation"]
    assert len(skill.capabilities) == 2
    assert len(skill.when_to_use) == 2
    assert len(skill.approach) == 3
    assert len(skill.constraints) == 2


def test_get_skill(skill_dir: Path) -> None:
    loader = SkillLoader(skill_dirs=[skill_dir])
    skill = loader.get("code-generation")
    assert skill.name == "code-generation"


def test_get_nonexistent_skill(skill_dir: Path) -> None:
    loader = SkillLoader(skill_dirs=[skill_dir])
    with pytest.raises(SkillNotFoundError):
        loader.get("nonexistent")


def test_list_skills(skill_dir: Path) -> None:
    loader = SkillLoader(skill_dirs=[skill_dir])
    names = loader.list_skills()
    assert "code-generation" in names


def test_skill_keywords(skill_dir: Path) -> None:
    loader = SkillLoader(skill_dirs=[skill_dir])
    skill = loader.get("code-generation")
    keywords = skill.keywords
    assert "python" in keywords or "code" in keywords
    assert len(keywords) > 0


def test_empty_dir(tmp_path: Path) -> None:
    loader = SkillLoader(skill_dirs=[tmp_path])
    skills = loader.load_all()
    assert len(skills) == 0
