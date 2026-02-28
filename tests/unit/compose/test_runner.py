"""Tests for compose runner (CopilotEngine-based)."""

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

    def test_topological_sort(self, mock_config, events, simple_compose):
        runner = ComposeRunner(config=mock_config, events=events, compose=simple_compose)
        order = runner._topological_sort()
        # worker-a should come before worker-b (worker-b depends on worker-a)
        assert order.index("worker-a") < order.index("worker-b")

    def test_topological_sort_no_deps(self, mock_config, events):
        compose = ComposeConfig(
            team="no-deps",
            agents={
                "a": ComposeAgentConfig(role="A"),
                "b": ComposeAgentConfig(role="B"),
                "c": ComposeAgentConfig(role="C"),
            },
        )
        runner = ComposeRunner(config=mock_config, events=events, compose=compose)
        order = runner._topological_sort()
        assert len(order) == 3

    def test_output_dir(self, mock_config, events):
        compose = ComposeConfig(
            team="test",
            output="/custom/output",
            agents={"w": ComposeAgentConfig(role="W")},
        )
        runner = ComposeRunner(config=mock_config, events=events, compose=compose)
        assert runner._output_dir == Path("/custom/output").resolve()

    def test_build_agent_skill_context(self, mock_config, events, simple_compose):
        runner = ComposeRunner(config=mock_config, events=events, compose=simple_compose)
        # Should not raise even with skills that aren't loaded
        context = runner._build_agent_skill_context(["code-generation", "nonexistent"])
        assert isinstance(context, str)
