"""Integration tests for Phase 5 — Skills + Compose pipeline (V3: no strategies)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.compose.parser import parse_compose_file
from hauba.compose.runner import ComposeRunner
from hauba.core.constants import BUNDLED_SKILLS_DIR
from hauba.core.events import EventEmitter
from hauba.core.types import ComposeConfig
from hauba.skills.loader import SkillLoader
from hauba.skills.matcher import SkillMatcher


class TestSkillLoading:
    """Test that bundled skills load correctly."""

    def test_load_bundled_skills(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        skills = loader.load_all()
        assert len(skills) >= 17, f"Expected at least 17 bundled skills, got {len(skills)}"

    def test_all_original_skill_names(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        skills = loader.load_all()
        expected = {
            "full-stack-engineering",
            "code-generation",
            "debugging-and-repair",
            "data-engineering",
            "api-design-and-integration",
            "devops-and-deployment",
            "testing-and-quality",
            "security-hardening",
            "research-and-analysis",
            "refactoring-and-migration",
        }
        assert expected.issubset(set(skills.keys())), (
            f"Missing skills: {expected - set(skills.keys())}"
        )

    def test_new_workstation_skill_names(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        skills = loader.load_all()
        expected = {
            "video-editing",
            "image-generation",
            "data-processing",
            "web-scraping",
            "automation-and-scripting",
            "document-generation",
            "machine-learning",
        }
        assert expected.issubset(set(skills.keys())), (
            f"Missing new skills: {expected - set(skills.keys())}"
        )

    def test_skills_have_capabilities(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        skills = loader.load_all()
        for name, skill in skills.items():
            assert skill.capabilities, f"Skill '{name}' has no capabilities"
            assert skill.when_to_use, f"Skill '{name}' has no when_to_use"

    def test_new_skills_have_tools_required(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        skills = loader.load_all()
        skills_with_tools = [
            "video-editing",
            "image-generation",
            "data-processing",
            "web-scraping",
            "document-generation",
            "machine-learning",
        ]
        for name in skills_with_tools:
            skill = skills.get(name)
            assert skill is not None, f"Skill '{name}' not found"
            assert skill.tools_required, f"Skill '{name}' has no tools_required"

    def test_skills_with_playbooks(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        skills = loader.load_all()
        skills_with_playbooks = [
            "full-stack-engineering",
            "debugging-and-repair",
            "data-engineering",
            "api-design-and-integration",
            "refactoring-and-migration",
            "research-and-analysis",
        ]
        for name in skills_with_playbooks:
            skill = skills.get(name)
            assert skill is not None, f"Skill '{name}' not found"
            assert skill.playbook, f"Skill '{name}' has no playbook"

    def test_skill_matching(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        matcher = SkillMatcher(loader)

        matches = matcher.match("build a full-stack web application with API")
        assert len(matches) > 0
        skill_names = {m.skill.name for m in matches}
        assert (
            "full-stack-engineering" in skill_names or "api-design-and-integration" in skill_names
        )

    def test_skill_matching_debug(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        matcher = SkillMatcher(loader)

        matches = matcher.match("debug and fix this broken crash error bug")
        assert len(matches) > 0
        skill_names = {m.skill.name for m in matches}
        assert "debugging-and-repair" in skill_names

    def test_skill_matching_video(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        matcher = SkillMatcher(loader)

        matches = matcher.match("edit this video and add subtitles")
        assert len(matches) > 0
        skill_names = {m.skill.name for m in matches}
        assert "video-editing" in skill_names

    def test_skill_matching_data(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        matcher = SkillMatcher(loader)

        matches = matcher.match("analyze this CSV data and create a chart")
        assert len(matches) > 0


class TestComposeWithBundled:
    """Test compose pipeline with bundled skills."""

    def test_parse_example_compose(self):
        example = Path(__file__).resolve().parent.parent.parent / "hauba.yaml.example"
        if not example.exists():
            pytest.skip("hauba.yaml.example not found")

        config = parse_compose_file(example)
        assert config.team == "my-project"
        assert len(config.agents) >= 3

    def test_compose_runner_initialization(self):
        from unittest.mock import MagicMock

        from hauba.core.types import ComposeAgentConfig

        config = MagicMock()
        events = EventEmitter()
        compose = ComposeConfig(
            team="test",
            agents={
                "dev": ComposeAgentConfig(
                    role="Developer",
                    skills=["code-generation"],
                ),
            },
        )
        runner = ComposeRunner(config=config, events=events, compose=compose)
        assert runner.team_name == "test"
        assert runner.get_agent_skills("dev") == ["code-generation"]
