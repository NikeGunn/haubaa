"""Phase 2 integration test — Director + TaskLedger + multi-agent pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hauba.agents.director import DirectorAgent
from hauba.core.config import ConfigManager
from hauba.core.events import EventEmitter
from hauba.core.types import LLMResponse

MOCK_DELIBERATION_RESPONSE = """UNDERSTANDING:
The user wants to create a Python project with two files.

APPROACH:
Create main.py and utils.py in the workspace.

STEPS:
1. Create utils.py with a helper function [tool: files]
2. Create main.py that imports from utils [tool: files]

RISKS:
- None for simple file creation

CONFIDENCE: 0.9
"""

MOCK_TOOL_CALL_UTILS = """TOOL: files
ARGS:
action: write
path: {path}/utils.py
content: def greet(name): return f"Hello, {{name}}!"
"""

MOCK_TOOL_CALL_MAIN = """TOOL: files
ARGS:
action: write
path: {path}/main.py
content: from utils import greet; print(greet("World"))
"""

MOCK_STATUS = """STATUS: done - File created successfully."""


@pytest.fixture
def config(tmp_path: Path) -> ConfigManager:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
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
    }))
    return ConfigManager(settings_path)


@pytest.mark.asyncio
async def test_director_creates_ledger_and_tracks_steps(
    config: ConfigManager, tmp_path: Path
) -> None:
    """Test that Director creates a TaskLedger and tracks step completion."""
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

    call_count = 0

    async def mock_complete(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(content=MOCK_DELIBERATION_RESPONSE, model="mock", tokens_used=100)
        elif call_count == 2:
            return LLMResponse(
                content=MOCK_TOOL_CALL_UTILS.format(path=str(work_dir)),
                model="mock", tokens_used=50,
            )
        elif call_count == 3:
            return LLMResponse(content=MOCK_STATUS, model="mock", tokens_used=20)
        elif call_count == 4:
            return LLMResponse(
                content=MOCK_TOOL_CALL_MAIN.format(path=str(work_dir)),
                model="mock", tokens_used=50,
            )
        else:
            return LLMResponse(content=MOCK_STATUS, model="mock", tokens_used=20)

    director = DirectorAgent(config=config, events=events)
    director._llm.complete = mock_complete
    director._deliberation._llm.complete = mock_complete
    director._deliberation._think_time = 0.0

    result = await director.run("create a Python project with utils and main")

    # Verify task succeeded
    assert result.success, f"Expected success but got: {result.error}"

    # Verify TaskLedger was created and gates passed
    assert "ledger.created" in ledger_events
    assert "ledger.task_started" in ledger_events
    assert "ledger.task_completed" in ledger_events

    # Verify ledger state
    assert director._ledger is not None
    assert director._ledger.task_count == 2
    assert director._ledger.is_complete

    # Verify TODO.md was written
    assert director._workspace is not None
    todo_path = director._workspace / "todo.md"
    assert todo_path.exists()
    todo_content = todo_path.read_text()
    assert "2/2" in todo_content  # All tasks verified

    # Verify ledger.json persisted
    ledger_path = director._workspace / "ledger.json"
    assert ledger_path.exists()

    # Verify WAL was written
    wal_path = director._workspace / "wal.log"
    assert wal_path.exists()

    # Verify files were created
    assert (work_dir / "utils.py").exists()
    assert (work_dir / "main.py").exists()

    print("\n✓ Phase 2 E2E passed!")
    print(f"  Ledger: {director._ledger!r}")
    print(f"  Ledger events: {ledger_events}")
    print(f"  LLM calls: {call_count}")


@pytest.mark.asyncio
async def test_director_review_runs_gate_check(
    config: ConfigManager, tmp_path: Path
) -> None:
    """Test that Director's review phase runs Gate 4 and Gate 5."""
    events = EventEmitter()
    work_dir = tmp_path / "workspace"
    work_dir.mkdir()

    gate_events: list[str] = []

    async def track_gates(event):
        gate_events.append(f"{event.topic}:{event.data.get('gate', '')}")

    events.on("ledger.gate_passed", track_gates)
    events.on("ledger.gate_failed", track_gates)

    call_count = 0

    async def mock_complete(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(content=MOCK_DELIBERATION_RESPONSE, model="mock", tokens_used=100)
        elif call_count in (2, 4):
            path_str = str(work_dir)
            if call_count == 2:
                return LLMResponse(
                    content=MOCK_TOOL_CALL_UTILS.format(path=path_str),
                    model="mock", tokens_used=50,
                )
            return LLMResponse(
                content=MOCK_TOOL_CALL_MAIN.format(path=path_str),
                model="mock", tokens_used=50,
            )
        else:
            return LLMResponse(content=MOCK_STATUS, model="mock", tokens_used=20)

    director = DirectorAgent(config=config, events=events)
    director._llm.complete = mock_complete
    director._deliberation._llm.complete = mock_complete
    director._deliberation._think_time = 0.0

    result = await director.run("create a project")

    assert result.success
    # Gate 4 (delivery) and Gate 5 (reconciliation) should have passed
    gate_types = [e.split(":")[1] for e in gate_events]
    assert "delivery" in gate_types
    assert "reconciliation" in gate_types
