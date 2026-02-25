"""E2E integration test — full pipeline with mocked LLM."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hauba.agents.director import DirectorAgent
from hauba.core.config import ConfigManager
from hauba.core.events import EventEmitter
from hauba.core.types import LLMResponse, LLMResponseWithTools, LLMToolCall

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


@pytest.mark.asyncio
async def test_full_pipeline_creates_hello_world(config: ConfigManager, tmp_path: Path) -> None:
    """Test: hauba run 'create a Python hello world' → file created."""
    events = EventEmitter()

    # Track emitted events
    emitted: list[str] = []

    async def track_all(event):
        emitted.append(event.topic)

    events.on("*", track_all)

    work_dir = tmp_path / "workspace"
    work_dir.mkdir()

    # Mock deliberation LLM (uses complete() — no tools)
    async def mock_complete(messages, **kwargs):
        return LLMResponse(
            content=MOCK_DELIBERATION_RESPONSE,
            model="mock",
            tokens_used=100,
        )

    # Mock agentic loop LLM (uses complete_with_tools())
    tool_call_count = 0

    async def mock_complete_with_tools(messages, tools=None, **kwargs):
        nonlocal tool_call_count
        tool_call_count += 1
        if tool_call_count == 1:
            # First call: create the hello.py file
            return LLMResponseWithTools(
                content="",
                tool_calls=[
                    LLMToolCall(
                        id="call_1",
                        name="files",
                        arguments={
                            "action": "write",
                            "path": str(work_dir / "hello.py"),
                            "content": 'print("Hello, World!")',
                        },
                    )
                ],
                model="mock",
                tokens_used=50,
            )
        else:
            # Second call: done — return text summary
            return LLMResponseWithTools(
                content="Created hello.py with a Hello World program.",
                tool_calls=[],
                model="mock",
                tokens_used=20,
            )

    director = DirectorAgent(config=config, events=events, workspace=work_dir)

    # Patch LLM methods
    director._llm.complete = mock_complete
    director._llm.complete_with_tools = mock_complete_with_tools
    director._deliberation._llm.complete = mock_complete
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
    print(f"  Tool calls: {tool_call_count}")
    print(f"  Events emitted: {len(emitted)}")


@pytest.mark.asyncio
async def test_cli_status(config: ConfigManager) -> None:
    """Test that status command works with valid config."""
    assert config.settings.owner_name == "TestUser"
    assert config.settings.llm.provider == "anthropic"
