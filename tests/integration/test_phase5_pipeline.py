"""Integration tests for Phase 5 — Compose + Skills pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.compose.parser import parse_compose_file
from hauba.compose.runner import ComposeRunner
from hauba.core.constants import BUNDLED_SKILLS_DIR, BUNDLED_STRATEGIES_DIR
from hauba.core.events import EventEmitter
from hauba.core.types import ComposeConfig
from hauba.skills.loader import SkillLoader
from hauba.skills.matcher import SkillMatcher
from hauba.skills.strategy import StrategyEngine


class TestSkillLoading:
    """Test that bundled skills load correctly."""

    def test_load_bundled_skills(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        skills = loader.load_all()
        assert len(skills) >= 10, f"Expected at least 10 bundled skills, got {len(skills)}"

    def test_all_skill_names(self):
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
        assert expected.issubset(set(skills.keys())), f"Missing skills: {expected - set(skills.keys())}"

    def test_skills_have_capabilities(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        skills = loader.load_all()
        for name, skill in skills.items():
            assert skill.capabilities, f"Skill '{name}' has no capabilities"
            assert skill.when_to_use, f"Skill '{name}' has no when_to_use"

    def test_skill_matching(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        matcher = SkillMatcher(loader)

        matches = matcher.match("build a full-stack web application with API")
        assert len(matches) > 0
        skill_names = {m.skill.name for m in matches}
        assert "full-stack-engineering" in skill_names or "api-design-and-integration" in skill_names

    def test_skill_matching_debug(self):
        loader = SkillLoader(skill_dirs=[BUNDLED_SKILLS_DIR])
        matcher = SkillMatcher(loader)

        matches = matcher.match("debug and fix this broken crash error bug")
        assert len(matches) > 0
        skill_names = {m.skill.name for m in matches}
        assert "debugging-and-repair" in skill_names


class TestStrategyLoading:
    """Test that bundled strategies load correctly."""

    def test_load_bundled_strategies(self):
        engine = StrategyEngine(strategy_dirs=[BUNDLED_STRATEGIES_DIR])
        strategies = engine.load_all()
        assert len(strategies) >= 6, f"Expected at least 6 strategies, got {len(strategies)}"

    def test_all_strategy_names(self):
        engine = StrategyEngine(strategy_dirs=[BUNDLED_STRATEGIES_DIR])
        strategies = engine.load_all()
        expected = {
            "saas-building",
            "data-pipeline",
            "bug-fixing",
            "api-development",
            "code-review-and-refactor",
            "research-and-prototype",
        }
        assert expected.issubset(set(strategies.keys())), f"Missing strategies: {expected - set(strategies.keys())}"

    def test_strategies_have_milestones(self):
        engine = StrategyEngine(strategy_dirs=[BUNDLED_STRATEGIES_DIR])
        strategies = engine.load_all()
        for name, strategy in strategies.items():
            assert strategy.milestones, f"Strategy '{name}' has no milestones"
            assert strategy.agents, f"Strategy '{name}' has no agents"

    def test_strategy_to_milestones(self):
        engine = StrategyEngine(strategy_dirs=[BUNDLED_STRATEGIES_DIR])
        strategy = engine.get("saas-building")
        assert strategy is not None

        milestones = strategy.to_milestone_objects()
        assert len(milestones) >= 4
        # First milestone should have no dependencies
        assert milestones[0].dependencies == []

    def test_strategy_domain_matching(self):
        engine = StrategyEngine(strategy_dirs=[BUNDLED_STRATEGIES_DIR])
        strategy = engine.match_domain("build a saas application with billing")
        assert strategy is not None
        assert strategy.name == "saas-building"


class TestComposeWithBundled:
    """Test compose pipeline with bundled skills and strategies."""

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
