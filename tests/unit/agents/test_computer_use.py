"""Tests for ComputerUseAgent — screenshot-analyze-act loop."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hauba.agents.computer_use import ComputerUseAgent
from hauba.core.config import ConfigManager
from hauba.core.events import EventEmitter
from hauba.core.types import LLMResponse, ToolResult


@pytest.fixture
def config(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    return ConfigManager(settings_path)


@pytest.fixture
def events():
    return EventEmitter()


@pytest.fixture
def agent(config, events):
    return ComputerUseAgent(config=config, events=events)


# --- Deliberation ---

async def test_deliberate_returns_plan(agent):
    plan = await agent.deliberate("Open calculator", "task-123")
    assert plan.task_id == "task-123"
    assert len(plan.steps) == 1
    assert "calculator" in plan.steps[0].description.lower()


# --- Parse action ---

def test_parse_action_json(agent):
    text = '{"action": "click", "x": 100, "y": 200, "reasoning": "click button"}'
    result = agent._parse_action(text)
    assert result is not None
    assert result["action"] == "click"
    assert result["x"] == 100


def test_parse_action_code_block(agent):
    text = '''Here is the action:
```json
{"action": "type", "text": "hello", "reasoning": "typing"}
```
'''
    result = agent._parse_action(text)
    assert result is not None
    assert result["action"] == "type"
    assert result["text"] == "hello"


def test_parse_action_embedded(agent):
    text = 'I will now perform {"action": "done", "reasoning": "complete"} action.'
    result = agent._parse_action(text)
    assert result is not None
    assert result["action"] == "done"


def test_parse_action_invalid(agent):
    result = agent._parse_action("No JSON here at all")
    assert result is None


# --- Execute loop ---

async def test_execute_done_immediately(agent):
    """LLM says done on first iteration — should complete successfully."""
    # Mock screen capture
    mock_capture_result = ToolResult(
        tool_name="screen", success=True, output="Screenshot saved: /tmp/shot.png"
    )
    agent._screen.execute = AsyncMock(return_value=mock_capture_result)

    # Mock LLM to return "done"
    done_response = LLMResponse(
        content='{"action": "done", "reasoning": "Task is already complete"}',
        model="test",
    )
    agent._llm.complete = AsyncMock(return_value=done_response)
    agent._delay = 0  # No delay in tests

    plan = await agent.deliberate("check screen", "task-test")
    result = await agent.execute(plan)
    assert result.success
    assert "1 iterations" in result.value


async def test_execute_click_then_done(agent):
    """LLM clicks once, then says done."""
    capture_result = ToolResult(
        tool_name="screen", success=True, output="Screenshot saved: /tmp/shot.png"
    )
    click_result = ToolResult(
        tool_name="screen", success=True, output="Clicked (100, 200) [left]"
    )

    # Track call count to return different results
    call_count = 0

    async def mock_screen_execute(**kwargs):
        nonlocal call_count
        action = kwargs.get("action", "")
        if action == "capture":
            return capture_result
        call_count += 1
        return click_result

    agent._screen.execute = mock_screen_execute

    # First LLM call: click, second: done
    responses = [
        LLMResponse(content='{"action": "click", "x": 100, "y": 200, "reasoning": "click btn"}', model="test"),
        LLMResponse(content='{"action": "done", "reasoning": "done"}', model="test"),
    ]
    call_idx = 0

    async def mock_complete(messages, **kwargs):
        nonlocal call_idx
        resp = responses[min(call_idx, len(responses) - 1)]
        call_idx += 1
        return resp

    agent._llm.complete = mock_complete
    agent._delay = 0

    plan = await agent.deliberate("click button", "task-test2")
    result = await agent.execute(plan)
    assert result.success


async def test_execute_max_iterations(agent):
    """Should fail after max iterations."""
    capture_result = ToolResult(
        tool_name="screen", success=True, output="Screenshot saved: /tmp/shot.png"
    )
    click_result = ToolResult(
        tool_name="screen", success=True, output="Clicked (0, 0)"
    )

    async def mock_screen_execute(**kwargs):
        action = kwargs.get("action", "")
        if action == "capture":
            return capture_result
        return click_result

    agent._screen.execute = mock_screen_execute
    agent._max_iterations = 3
    agent._delay = 0

    click_response = LLMResponse(
        content='{"action": "click", "x": 0, "y": 0, "reasoning": "still working"}',
        model="test",
    )
    agent._llm.complete = AsyncMock(return_value=click_response)

    plan = await agent.deliberate("never-ending task", "task-max")
    result = await agent.execute(plan)
    assert not result.success
    assert "Max iterations" in result.error


async def test_execute_screenshot_failure(agent):
    """If screenshot fails, execution stops with error."""
    fail_result = ToolResult(
        tool_name="screen", success=False, error="Display not available"
    )
    agent._screen.execute = AsyncMock(return_value=fail_result)
    agent._delay = 0

    plan = await agent.deliberate("test", "task-fail")
    result = await agent.execute(plan)
    assert not result.success
    assert "Screenshot failed" in result.error


# --- Review ---

async def test_review_passes_through(agent):
    from hauba.core.types import Result
    r = Result.ok("all good")
    reviewed = await agent.review(r)
    assert reviewed.success
    assert reviewed.value == "all good"
