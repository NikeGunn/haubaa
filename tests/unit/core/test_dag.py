"""Tests for DAG Executor — parallel milestone execution with WAIT architecture."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hauba.core.dag import DAGExecutor
from hauba.core.events import EventEmitter
from hauba.core.types import Milestone, TaskStatus


@pytest.fixture
def config() -> MagicMock:
    cfg = MagicMock()
    cfg.settings = MagicMock()
    cfg.settings.llm = MagicMock()
    cfg.settings.llm.provider = "anthropic"
    cfg.settings.llm.model = "claude-sonnet-4-5-20250929"
    cfg.settings.llm.api_key = "test-key"
    cfg.settings.llm.base_url = None
    cfg.settings.llm.max_tokens = 4096
    return cfg


@pytest.fixture
def events() -> EventEmitter:
    return EventEmitter()


def test_add_milestones(config: MagicMock, events: EventEmitter) -> None:
    dag = DAGExecutor(config, events)
    m1 = Milestone(id="m1", description="First")
    m2 = Milestone(id="m2", description="Second", dependencies=["m1"])
    dag.add_milestones([m1, m2])

    assert len(dag._milestones) == 2


def test_get_ready_milestones(config: MagicMock, events: EventEmitter) -> None:
    dag = DAGExecutor(config, events)
    m1 = Milestone(id="m1", description="First")
    m2 = Milestone(id="m2", description="Second", dependencies=["m1"])
    m3 = Milestone(id="m3", description="Third")
    dag.add_milestones([m1, m2, m3])

    ready = dag.get_ready_milestones()
    ready_ids = [m.id for m in ready]
    assert "m1" in ready_ids
    assert "m3" in ready_ids
    assert "m2" not in ready_ids  # m2 depends on m1


def test_validate_dag_no_cycles(config: MagicMock, events: EventEmitter) -> None:
    dag = DAGExecutor(config, events)
    dag.add_milestones([
        Milestone(id="a", description="A"),
        Milestone(id="b", description="B", dependencies=["a"]),
        Milestone(id="c", description="C", dependencies=["b"]),
    ])
    assert dag.validate_dag() is True


def test_validate_dag_detects_cycle(config: MagicMock, events: EventEmitter) -> None:
    dag = DAGExecutor(config, events)
    dag.add_milestones([
        Milestone(id="a", description="A", dependencies=["c"]),
        Milestone(id="b", description="B", dependencies=["a"]),
        Milestone(id="c", description="C", dependencies=["b"]),
    ])
    assert dag.validate_dag() is False


def test_progress(config: MagicMock, events: EventEmitter) -> None:
    dag = DAGExecutor(config, events)
    m1 = Milestone(id="m1", description="First")
    m2 = Milestone(id="m2", description="Second")
    dag.add_milestones([m1, m2])

    assert dag.progress == (0, 2)

    m1.status = TaskStatus.VERIFIED
    assert dag.progress == (1, 2)


@pytest.mark.asyncio
async def test_execute_empty_dag(config: MagicMock, events: EventEmitter) -> None:
    dag = DAGExecutor(config, events)
    result = await dag.execute()
    assert result.success
    assert "No milestones" in (result.value or "")
