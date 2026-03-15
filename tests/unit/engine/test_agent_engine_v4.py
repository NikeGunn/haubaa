"""Tests for AgentEngine V4 — custom agent loop, tool execution, streaming."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hauba.engine.agent_engine import AgentEngine, StreamEvent
from hauba.engine.types import EngineConfig, EngineResult, ProviderType

# --- StreamEvent tests ---


def test_stream_event_defaults() -> None:
    """StreamEvent auto-sets timestamp."""
    event = StreamEvent(type="test")
    assert event.type == "test"
    assert event.data == {}
    assert event.timestamp > 0


def test_stream_event_with_data() -> None:
    """StreamEvent stores data dict."""
    event = StreamEvent(type="tool_start", data={"tool": "bash", "input": "ls"})
    assert event.data["tool"] == "bash"
    assert event.data["input"] == "ls"


# --- AgentEngine init tests ---


def test_engine_init() -> None:
    """Engine initializes with config."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test-key")
    engine = AgentEngine(config)
    assert engine._config.api_key == "test-key"
    assert not engine._started
    assert engine._total_turns == 0


def test_engine_init_with_skill_context() -> None:
    """Engine stores skill context."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config, skill_context="## Test Skill\n- Build APIs")
    assert "Test Skill" in engine._skill_context


def test_engine_is_available() -> None:
    """Engine checks litellm availability."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config)
    # Returns bool (True if litellm installed, False otherwise)
    assert isinstance(engine.is_available, bool)


# --- Event system tests ---


def test_engine_event_subscription() -> None:
    """Can subscribe and unsubscribe from events."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config)

    events_received: list = []

    def handler(event):
        events_received.append(event)

    unsub = engine.on_event(handler)
    engine._emit("test_event", {"foo": "bar"})

    assert len(events_received) == 1
    assert events_received[0].type == "test_event"
    assert events_received[0].data["foo"] == "bar"

    # Unsubscribe
    unsub()
    engine._emit("another_event")
    assert len(events_received) == 1  # No more events


def test_engine_event_handler_error_swallowed() -> None:
    """Broken event handlers don't crash the engine."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config)

    def bad_handler(event):
        raise ValueError("boom")

    engine.on_event(bad_handler)
    # Should not raise
    engine._emit("test")


# --- Engine start/stop tests ---


@pytest.mark.asyncio
async def test_engine_start_creates_components() -> None:
    """Engine start initializes LLM, tools, and context."""
    config = EngineConfig(
        provider=ProviderType.ANTHROPIC,
        api_key="test-key",
        model="claude-test",
    )
    engine = AgentEngine(config)

    await engine.start()

    assert engine._started
    assert engine._llm is not None
    assert engine._tools is not None
    assert engine._context is not None
    assert engine._context.system_prompt != ""

    await engine.stop()
    assert not engine._started
    assert engine._llm is None


@pytest.mark.asyncio
async def test_engine_start_idempotent() -> None:
    """Starting an already-started engine is a no-op."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config)

    await engine.start()
    tools_ref = engine._tools
    await engine.start()  # Should not reinitialize
    assert engine._tools is tools_ref

    await engine.stop()


# --- Execute tests (mocked LLM) ---


@pytest.mark.asyncio
async def test_engine_execute_simple_text() -> None:
    """Engine returns text when LLM responds without tool calls."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config)

    await engine.start()

    # Mock the LLM to return a simple text response
    from hauba.engine.llm import LLMResponse

    mock_response = LLMResponse(
        text="Hello! I'm ready to help.",
        tool_calls=[],
        input_tokens=10,
        output_tokens=20,
    )
    engine._llm.complete = AsyncMock(return_value=mock_response)  # type: ignore

    result = await engine.execute("Say hello")

    assert result.success
    assert "Hello" in result.output
    assert engine._total_turns == 1

    await engine.stop()


@pytest.mark.asyncio
async def test_engine_execute_with_tool_call() -> None:
    """Engine executes tool calls and loops back to LLM."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config)

    await engine.start()

    from hauba.engine.llm import LLMResponse

    # First call: LLM wants to use a tool
    tool_response = LLMResponse(
        text="Let me list the files.",
        tool_calls=[
            {
                "id": "call_1",
                "name": "read_file",
                "input": {"path": "nonexistent.txt"},
            }
        ],
        input_tokens=10,
        output_tokens=20,
    )

    # Second call: LLM responds with text only (done)
    final_response = LLMResponse(
        text="The file doesn't exist. Let me create it.",
        tool_calls=[],
        input_tokens=10,
        output_tokens=20,
    )

    engine._llm.complete = AsyncMock(side_effect=[tool_response, final_response])  # type: ignore

    result = await engine.execute("Read a file")

    assert result.success
    assert engine._total_turns == 2

    await engine.stop()


@pytest.mark.asyncio
async def test_engine_execute_timeout() -> None:
    """Engine returns failure on timeout."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config)

    await engine.start()

    # Mock LLM that takes forever
    async def slow_complete(**kwargs):
        import asyncio

        await asyncio.sleep(100)

    engine._llm.complete = slow_complete  # type: ignore

    result = await engine.execute("slow task", timeout=0.1)

    assert not result.success
    assert "timed out" in result.error.lower()

    await engine.stop()


@pytest.mark.asyncio
async def test_engine_execute_error() -> None:
    """Engine returns failure on LLM error."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config)

    await engine.start()

    engine._llm.complete = AsyncMock(side_effect=RuntimeError("API error"))  # type: ignore

    result = await engine.execute("broken task")

    assert not result.success
    assert "API error" in result.error

    await engine.stop()


# --- EngineResult tests ---


def test_engine_result_ok() -> None:
    """EngineResult.ok() creates success result."""
    r = EngineResult.ok(output="done", session_id="s123")
    assert r.success
    assert r.output == "done"
    assert r.session_id == "s123"


def test_engine_result_fail() -> None:
    """EngineResult.fail() creates failure result."""
    r = EngineResult.fail("broke")
    assert not r.success
    assert r.error == "broke"


# --- Context manager tests ---


@pytest.mark.asyncio
async def test_engine_context_manager() -> None:
    """Engine supports async context manager."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")

    async with AgentEngine(config) as engine:
        assert engine._started

    assert not engine._started


# --- Streamed execution tests ---


@pytest.mark.asyncio
async def test_engine_execute_streamed_events() -> None:
    """Streamed execution yields proper events."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = AgentEngine(config)

    await engine.start()

    from hauba.engine.llm import LLMResponse, StreamChunk

    # Mock streaming to return a simple response
    async def mock_stream(**kwargs):
        yield StreamChunk(text="Hello ")
        yield StreamChunk(text="world!")
        yield StreamChunk(
            is_final=True,
            final_response=LLMResponse(text="Hello world!", tool_calls=[]),
        )

    engine._llm.stream = mock_stream  # type: ignore

    events = []
    async for event in engine.execute_streamed("test"):
        events.append(event)

    event_types = [e.type for e in events]
    assert "task_started" in event_types
    assert "text_delta" in event_types
    assert "task_completed" in event_types

    await engine.stop()
