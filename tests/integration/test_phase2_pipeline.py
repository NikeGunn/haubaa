"""Phase 2 integration test — Director + TaskLedger + multi-agent pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hauba.agents.director import DirectorAgent
from hauba.core.config import ConfigManager
from hauba.core.events import EventEmitter
from hauba.core.types import LLMResponse, LLMResponseWithTools

# Deliberation response with 5+ steps to trigger multi-agent path + ledger
MOCK_COMPLEX_DELIBERATION = """UNDERSTANDING:
The user wants to create a complex Python project.

APPROACH:
Create multiple files with proper structure.

STEPS:
1. Create project directory structure [tool: bash]
2. Create utils.py [tool: files]
3. Create models.py [tool: files]
4. Create main.py [tool: files]
5. Create requirements.txt [tool: files]

RISKS:
- None

CONFIDENCE: 0.9
"""


@pytest.fixture
def config(tmp_path: Path) -> ConfigManager:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5-20250929",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                    "api_key": "test-key",
                    "base_url": "",
                },
                "owner_name": "TestUser",
                "data_dir": "",
                "log_level": "INFO",
                "think_time": 0.0,
            }
        )
    )
    return ConfigManager(settings_path)


def _mock_complete():
    """Return a mock for LLMRouter.complete that returns deliberation text."""

    async def _complete(self, messages, **kwargs):
        return LLMResponse(content=MOCK_COMPLEX_DELIBERATION, model="mock", tokens_used=100)

    return _complete


def _mock_complete_with_tools():
    """Return a mock for LLMRouter.complete_with_tools — workers finish immediately."""

    async def _complete_with_tools(self, messages, tools=None, **kwargs):
        return LLMResponseWithTools(
            content="Task completed successfully.",
            tool_calls=[],
            model="mock",
            tokens_used=20,
        )

    return _complete_with_tools


@pytest.mark.asyncio
async def test_director_creates_ledger_and_tracks_steps(
    config: ConfigManager, tmp_path: Path
) -> None:
    """Test that Director creates a TaskLedger for complex tasks and tracks step completion."""
    events = EventEmitter()
    work_dir = tmp_path / "workspace"
    work_dir.mkdir()

    # Track ledger events
    ledger_events: list[str] = []

    async def track_ledger(event):
        ledger_events.append(event.topic)

    events.on("ledger.created", track_ledger)
    events.on("ledger.task_started", track_ledger)
    events.on("ledger.task_completed", track_ledger)
    events.on("ledger.gate_passed", track_ledger)

    # Patch LLMRouter at the class level so ALL instances (Director, SubAgent, Worker) use mocks
    with (
        patch("hauba.brain.llm.LLMRouter.complete", _mock_complete()),
        patch("hauba.brain.llm.LLMRouter.complete_with_tools", _mock_complete_with_tools()),
    ):
        director = DirectorAgent(config=config, events=events, workspace=work_dir)
        director._deliberation._think_time = 0.0

        result = await director.run("create a complex Python project")

    # Verify task succeeded
    assert result.success, f"Expected success but got: {result.error}"

    # Verify TaskLedger was created (only for complex tasks with 5+ steps)
    assert "ledger.created" in ledger_events
    assert director._ledger is not None
    assert director._ledger.task_count == 5

    # Verify WAL was written (WAL is stored in the agents dir, not workspace)
    assert director._wal is not None
    assert director._wal._path.exists()

    print("\n✓ Phase 2 E2E passed!")
    print(f"  Ledger: {director._ledger!r}")
    print(f"  Ledger events: {ledger_events}")


@pytest.mark.asyncio
async def test_director_review_runs_gate_check(config: ConfigManager, tmp_path: Path) -> None:
    """Test that Director's review phase runs Gate 4 and Gate 5 for complex tasks."""
    events = EventEmitter()
    work_dir = tmp_path / "workspace"
    work_dir.mkdir()

    gate_events: list[str] = []

    async def track_gates(event):
        gate_events.append(f"{event.topic}:{event.data.get('gate', '')}")

    events.on("ledger.gate_passed", track_gates)
    events.on("ledger.gate_failed", track_gates)

    # Patch LLMRouter at the class level so ALL instances use mocks
    with (
        patch("hauba.brain.llm.LLMRouter.complete", _mock_complete()),
        patch("hauba.brain.llm.LLMRouter.complete_with_tools", _mock_complete_with_tools()),
    ):
        director = DirectorAgent(config=config, events=events, workspace=work_dir)
        director._deliberation._think_time = 0.0

        result = await director.run("create a project")

    assert result.success, f"Expected success but got: {result.error}"

    # Gate 4 (delivery) and Gate 5 (reconciliation) should have passed
    gate_types = [e.split(":")[1] for e in gate_events]
    assert "delivery" in gate_types
    assert "reconciliation" in gate_types
