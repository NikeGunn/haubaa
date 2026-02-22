"""Tests for skill CLI commands."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from hauba.skills.cli import skill_app

runner = CliRunner()


@pytest.fixture
def skill_file(tmp_path):
    """Create a valid skill .md file."""
    f = tmp_path / "my-skill.md"
    f.write_text(
        """# Skill: my-skill

## Capabilities
- Does amazing things

## When To Use
- When you need amazing things

## Approach
1. Be amazing

## Constraints
- Don't be not amazing
""",
        encoding="utf-8",
    )
    return f


@pytest.fixture
def skills_dir(tmp_path):
    """Create a temp skills directory with a skill."""
    d = tmp_path / "skills"
    d.mkdir()
    skill = d / "test-skill.md"
    skill.write_text(
        """# Skill: test-skill

## Capabilities
- Testing capability

## When To Use
- During tests
""",
        encoding="utf-8",
    )
    return d


class TestSkillList:
    def test_list_with_bundled_skills(self):
        """List should find bundled skills from skills/core/."""
        result = runner.invoke(skill_app, ["list"])
        # Should not crash; may find bundled skills or show "No skills"
        assert result.exit_code == 0

    def test_list_with_skills_dir(self, skills_dir):
        """List should find skills in a custom directory."""
        with (
            patch("hauba.skills.cli.SKILLS_DIR", skills_dir),
            patch("hauba.skills.cli.BUNDLED_SKILLS_DIR", skills_dir.parent / "nonexistent"),
        ):
            result = runner.invoke(skill_app, ["list"])
            assert result.exit_code == 0
            assert "test-skill" in result.output


class TestSkillInstall:
    def test_install_skill(self, skill_file, tmp_path):
        dest_dir = tmp_path / "installed"
        dest_dir.mkdir()
        with patch("hauba.skills.cli.SKILLS_DIR", dest_dir):
            result = runner.invoke(skill_app, ["install", str(skill_file)])
            assert result.exit_code == 0
            assert "Installed" in result.output
            assert (dest_dir / "my-skill.md").exists()

    def test_install_file_not_found(self):
        result = runner.invoke(skill_app, ["install", "/nonexistent/file.md"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_install_non_md_file(self, tmp_path):
        f = tmp_path / "skill.txt"
        f.write_text("not a skill", encoding="utf-8")
        result = runner.invoke(skill_app, ["install", str(f)])
        assert result.exit_code == 1
        assert ".md" in result.output


class TestSkillCreate:
    def test_create_scaffold(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(skill_app, ["create", "my-new-skill"])
        assert result.exit_code == 0
        assert "Created" in result.output

        created = tmp_path / "my-new-skill.md"
        assert created.exists()
        content = created.read_text(encoding="utf-8")
        assert "# Skill: my-new-skill" in content
        assert "## Capabilities" in content
        assert "## Approach" in content

    def test_create_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "existing.md").write_text("exists", encoding="utf-8")
        result = runner.invoke(skill_app, ["create", "existing"])
        assert result.exit_code == 1
        assert "exists" in result.output.lower()


class TestSkillShow:
    def test_show_skill(self, skills_dir):
        with (
            patch("hauba.skills.cli.SKILLS_DIR", skills_dir),
            patch("hauba.skills.cli.BUNDLED_SKILLS_DIR", skills_dir.parent / "nonexistent"),
        ):
            result = runner.invoke(skill_app, ["show", "test-skill"])
            assert result.exit_code == 0
            assert "test-skill" in result.output

    def test_show_not_found(self, tmp_path):
        with (
            patch("hauba.skills.cli.SKILLS_DIR", tmp_path),
            patch("hauba.skills.cli.BUNDLED_SKILLS_DIR", tmp_path),
        ):
            result = runner.invoke(skill_app, ["show", "nonexistent-skill"])
            assert result.exit_code == 1
            assert "not found" in result.output.lower()
