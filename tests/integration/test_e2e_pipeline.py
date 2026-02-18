"""E2E integration test — full pipeline with mocked LLM."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hauba.agents.director import DirectorAgent
from hauba.core.config import ConfigManager
from hauba.core.events import EventEmitter
from hauba.core.types import LLMResponse

MOCK_DELIBERATION_RESPONSE = """UNDERSTANDING:
The user wants to create a simple Python hello world script.

APPROACH:
Create a single Python file with a hello world program.

STEPS:
1. Create the file hello.py with a hello world program [tool: files]

RISKS:
- None, this is a simple task

CONFIDENCE: 0.95
"""

MOCK_EXECUTE_RESPONSE = """TOOL: files
ARGS:
action: write
path: {path}/hello.py
content: print("Hello, World!")
"""

MOCK_STATUS_RESPONSE = """STATUS: done - File created successfully."""


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
async def test_full_pipeline_creates_hello_world(config: ConfigManager, tmp_path: Path) -> None:
    """Test: hauba run 'create a Python hello world' → file created."""
    events = EventEmitter()

    # Track emitted events
    emitted: list[str] = []

    async def track_all(event):
        emitted.append(event.topic)

    events.on("*", track_all)

    # Mock LLM responses
    call_count = 0
    work_dir = tmp_path / "workspace"
    work_dir.mkdir()

    async def mock_complete(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Deliberation response
            return LLMResponse(
                content=MOCK_DELIBERATION_RESPONSE,
                model="mock",
                tokens_used=100,
            )
        elif call_count == 2:
            # Execution: tool call
            return LLMResponse(
                content=MOCK_EXECUTE_RESPONSE.format(path=str(work_dir)),
                model="mock",
                tokens_used=50,
            )
        else:
            # Status assessment
            return LLMResponse(
                content=MOCK_STATUS_RESPONSE,
                model="mock",
                tokens_used=20,
            )

    director = DirectorAgent(config=config, events=events)

    # Patch the LLM router's complete method
    director._llm.complete = mock_complete
    # Patch deliberation engine's LLM too
    director._deliberation._llm.complete = mock_complete
    # Set think time to 0 for tests
    director._deliberation._think_time = 0.0

    result = await director.run("create a Python hello world")

    # Verify result
    assert result.success, f"Expected success but got: {result.error}"

    # Verify the file was actually created
    hello_file = work_dir / "hello.py"
    assert hello_file.exists(), "hello.py should have been created"
    content = hello_file.read_text()
    assert "Hello" in content or "hello" in content.lower()

    # Verify events were emitted
    assert "task.started" in emitted
    assert "agent.thinking" in emitted
    assert "agent.executing" in emitted
    assert "tool.called" in emitted
    assert "task.completed" in emitted

    print(f"\n✓ E2E test passed! Created {hello_file}")
    print(f"  File content: {content.strip()}")
    print(f"  LLM calls: {call_count}")
    print(f"  Events emitted: {len(emitted)}")


@pytest.mark.asyncio
async def test_cli_status(config: ConfigManager) -> None:
    """Test that status command works with valid config."""
    assert config.settings.owner_name == "TestUser"
    assert config.settings.llm.provider == "anthropic"
