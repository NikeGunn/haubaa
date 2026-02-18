"""Tests for compose runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hauba.compose.runner import ComposeRunner
from hauba.core.events import EventEmitter
from hauba.core.types import (
    ComposeAgentConfig,
    ComposeConfig,
)


@pytest.fixture
def events():
    return EventEmitter()


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.settings = MagicMock()
    config.settings.llm = MagicMock()
    config.settings.llm.provider = "test"
    config.settings.llm.model = "test-model"
    config.settings.llm.api_key = "test-key"
    return config


@pytest.fixture
def simple_compose():
    return ComposeConfig(
        team="test-team",
        description="Test team",
        agents={
            "worker-a": ComposeAgentConfig(
                role="Worker A",
                description="Does A things",
                skills=["code-generation"],
            ),
            "worker-b": ComposeAgentConfig(
                role="Worker B",
                description="Does B things",
                skills=["testing-and-quality"],
                depends_on=["worker-a"],
            ),
        },
    )


@pytest.fixture
def compose_with_strategy():
    return ComposeConfig(
        team="strategy-team",
        strategy="saas-building",
        agents={
            "backend": ComposeAgentConfig(role="Backend"),
        },
    )


class TestComposeRunner:
    def test_init(self, mock_config, events, simple_compose):
        runner = ComposeRunner(config=mock_config, events=events, compose=simple_compose)
        assert runner.team_name == "test-team"
        assert "worker-a" in runner.agent_names
        assert "worker-b" in runner.agent_names

    def test_agent_names(self, mock_config, events, simple_compose):
        runner = ComposeRunner(config=mock_config, events=events, compose=simple_compose)
        assert set(runner.agent_names) == {"worker-a", "worker-b"}

    def test_get_agent_skills(self, mock_config, events, simple_compose):
        runner = ComposeRunner(config=mock_config, events=events, compose=simple_compose)
        assert runner.get_agent_skills("worker-a") == ["code-generation"]
        assert runner.get_agent_skills("worker-b") == ["testing-and-quality"]
        assert runner.get_agent_skills("nonexistent") == []

    def test_build_milestones_from_agents(self, mock_config, events, simple_compose):
        runner = ComposeRunner(config=mock_config, events=events, compose=simple_compose)
        milestones = runner._build_milestones("build something")

        assert len(milestones) == 2
        names = {m.id for m in milestones}
        assert names == {"worker-a", "worker-b"}

        # Check dependencies mapped correctly
        worker_b = next(m for m in milestones if m.id == "worker-b")
        assert worker_b.dependencies == ["worker-a"]

        worker_a = next(m for m in milestones if m.id == "worker-a")
        assert worker_a.dependencies == []

    def test_build_milestones_with_strategy(self, mock_config, events, compose_with_strategy, tmp_path):
        """When a strategy is found, its milestones should be used."""
        strategy_dir = tmp_path / "strategies"
        strategy_dir.mkdir()
        strategy_yaml = strategy_dir / "saas-building.yaml"
        strategy_yaml.write_text("""
name: saas-building
description: "SaaS strategy"
domain: saas
milestones:
  - id: m1
    description: "First milestone"
    tasks:
      - "Task 1"
    dependencies: []
  - id: m2
    description: "Second milestone"
    tasks:
      - "Task 2"
    dependencies: [m1]
""", encoding="utf-8")

        runner = ComposeRunner(config=mock_config, events=events, compose=compose_with_strategy)
        runner._strategy_engine._strategy_dirs = [strategy_dir]
        runner._strategy_engine._loaded = False

        milestones = runner._build_milestones("build saas")
        assert len(milestones) == 2
        assert milestones[0].id == "m1"
        assert milestones[1].id == "m2"
        assert milestones[1].dependencies == ["m1"]

    def test_output_dir(self, mock_config, events):
        compose = ComposeConfig(
            team="test",
            output="/custom/output",
            agents={"w": ComposeAgentConfig(role="W")},
        )
        runner = ComposeRunner(config=mock_config, events=events, compose=compose)
        assert runner._output_dir == Path("/custom/output").resolve()
