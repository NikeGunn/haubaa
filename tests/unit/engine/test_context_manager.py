"""Tests for ContextManager — conversation context with auto-compaction."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hauba.engine.context import ContextManager
from hauba.engine.llm import LLMMessage

# --- Basic operations ---


def test_context_init() -> None:
    """ContextManager initializes with defaults."""
    ctx = ContextManager(system_prompt="You are helpful.")
    assert ctx.system_prompt == "You are helpful."
    assert ctx.message_count == 0
    assert ctx.max_context_tokens == 120_000


def test_add_user_message() -> None:
    """Adding user messages works."""
    ctx = ContextManager()
    ctx.add_user_message("hello")
    assert ctx.message_count == 1
    msgs = ctx.get_messages()
    assert msgs[0].role == "user"
    assert msgs[0].content == "hello"


def test_add_assistant_message() -> None:
    """Adding assistant messages works."""
    ctx = ContextManager()
    ctx.add_assistant_message(text="Hi there!")
    assert ctx.message_count == 1
    msgs = ctx.get_messages()
    assert msgs[0].role == "assistant"
    assert msgs[0].content == "Hi there!"


def test_add_assistant_message_with_tool_calls() -> None:
    """Assistant messages can include tool calls."""
    ctx = ContextManager()
    ctx.add_assistant_message(
        text="Let me check.",
        tool_calls=[{"id": "1", "name": "bash", "input": {"command": "ls"}}],
    )
    msgs = ctx.get_messages()
    assert msgs[0].tool_calls is not None
    assert len(msgs[0].tool_calls) == 1


def test_add_tool_result() -> None:
    """Adding tool results works."""
    ctx = ContextManager()
    ctx.add_tool_result(tool_use_id="call_1", content="file1.txt\nfile2.txt")
    msgs = ctx.get_messages()
    assert msgs[0].role == "tool"
    assert msgs[0].tool_call_id == "call_1"
    assert "file1.txt" in msgs[0].content


def test_add_tool_result_error() -> None:
    """Error tool results are prefixed."""
    ctx = ContextManager()
    ctx.add_tool_result(tool_use_id="call_1", content="not found", is_error=True)
    msgs = ctx.get_messages()
    assert "[ERROR]" in msgs[0].content


def test_get_messages_returns_copy() -> None:
    """get_messages returns a copy, not the internal list."""
    ctx = ContextManager()
    ctx.add_user_message("hello")
    msgs = ctx.get_messages()
    msgs.append(LLMMessage(role="user", content="injected"))
    assert ctx.message_count == 1  # Internal list not modified


def test_clear() -> None:
    """clear() removes all messages."""
    ctx = ContextManager()
    ctx.add_user_message("hello")
    ctx.add_assistant_message(text="hi")
    ctx.clear()
    assert ctx.message_count == 0


# --- Token estimation ---


def test_estimate_tokens_empty() -> None:
    """Empty context has tokens from system prompt only."""
    ctx = ContextManager(system_prompt="short")
    tokens = ctx.estimate_tokens()
    assert tokens > 0
    assert tokens < 10  # "short" is ~1 token


def test_estimate_tokens_with_messages() -> None:
    """Token estimate grows with messages."""
    ctx = ContextManager(system_prompt="Be helpful.")
    ctx.add_user_message("a" * 400)  # ~100 tokens
    tokens = ctx.estimate_tokens()
    assert tokens > 90


def test_estimate_tokens_with_tool_calls() -> None:
    """Token estimate includes tool calls."""
    ctx = ContextManager()
    ctx.add_assistant_message(
        text="Let me check.",
        tool_calls=[{"id": "1", "name": "bash", "input": {"command": "ls -la /var/log"}}],
    )
    tokens = ctx.estimate_tokens()
    assert tokens > 5  # Should include tool call data


# --- Compaction ---


def test_should_compact_false() -> None:
    """should_compact returns False when under threshold."""
    ctx = ContextManager(system_prompt="short", max_context_tokens=100_000)
    ctx.add_user_message("hello")
    assert not ctx.should_compact()


def test_should_compact_true() -> None:
    """should_compact returns True when over threshold."""
    ctx = ContextManager(system_prompt="short", max_context_tokens=100, compaction_threshold=0.5)
    # Add lots of content
    for _i in range(20):
        ctx.add_user_message("a" * 100)
        ctx.add_assistant_message(text="b" * 100)
    assert ctx.should_compact()


@pytest.mark.asyncio
async def test_compact_reduces_messages() -> None:
    """compact() summarizes old messages."""
    ctx = ContextManager(system_prompt="Be helpful.")

    # Add many messages
    for i in range(10):
        ctx.add_user_message(f"Question {i}")
        ctx.add_assistant_message(text=f"Answer {i}")

    initial_count = ctx.message_count

    # Mock LLM for summarization
    mock_llm = AsyncMock()
    mock_llm.summarize = AsyncMock(return_value="Summary of conversation so far.")

    await ctx.compact(mock_llm)

    assert ctx.message_count < initial_count
    # Should have a summary message + recent messages
    msgs = ctx.get_messages()
    assert any("summary" in str(m.content).lower() for m in msgs)


@pytest.mark.asyncio
async def test_compact_too_few_messages() -> None:
    """compact() does nothing with < 6 messages."""
    ctx = ContextManager()
    ctx.add_user_message("hello")
    ctx.add_assistant_message(text="hi")

    mock_llm = AsyncMock()
    await ctx.compact(mock_llm)

    # Should not have called summarize
    mock_llm.summarize.assert_not_called()
    assert ctx.message_count == 2


@pytest.mark.asyncio
async def test_compact_preserves_recent() -> None:
    """compact() keeps recent messages intact."""
    ctx = ContextManager()

    for i in range(10):
        ctx.add_user_message(f"Q{i}")
        ctx.add_assistant_message(text=f"A{i}")

    mock_llm = AsyncMock()
    mock_llm.summarize = AsyncMock(return_value="Summary")

    await ctx.compact(mock_llm)

    msgs = ctx.get_messages()
    # Last messages should be preserved
    last_msg = msgs[-1]
    assert last_msg.content in ["Q9", "A9"]


@pytest.mark.asyncio
async def test_compact_fallback_on_error() -> None:
    """compact() falls back to trimming on summarization error."""
    ctx = ContextManager()

    for i in range(10):
        ctx.add_user_message(f"Q{i}")
        ctx.add_assistant_message(text=f"A{i}")

    mock_llm = AsyncMock()
    mock_llm.summarize = AsyncMock(side_effect=RuntimeError("API error"))

    await ctx.compact(mock_llm)

    # Should still have reduced messages (via fallback)
    assert ctx.message_count < 20


# --- Compaction counter ---


@pytest.mark.asyncio
async def test_compaction_counter_increments() -> None:
    """Each compaction increments the counter."""
    ctx = ContextManager()

    for i in range(10):
        ctx.add_user_message(f"Q{i}")
        ctx.add_assistant_message(text=f"A{i}")

    mock_llm = AsyncMock()
    mock_llm.summarize = AsyncMock(return_value="Summary 1")

    assert ctx._compaction_count == 0
    await ctx.compact(mock_llm)
    assert ctx._compaction_count == 1

    # Add more messages and compact again
    for i in range(10):
        ctx.add_user_message(f"Q{i}")
        ctx.add_assistant_message(text=f"A{i}")

    mock_llm.summarize = AsyncMock(return_value="Summary 2")
    await ctx.compact(mock_llm)
    assert ctx._compaction_count == 2


# --- Session context injection ---


def test_update_session_context() -> None:
    """update_session_context appends session state to system prompt."""
    ctx = ContextManager(system_prompt="You are Hauba.\n\n## Tools")
    ctx.update_session_context("## Session State\nTurn 3. 5 tool calls.")

    assert "## Session State" in ctx.system_prompt
    assert "Turn 3" in ctx.system_prompt
    assert "You are Hauba." in ctx.system_prompt


def test_update_session_context_replaces_old() -> None:
    """Calling update_session_context twice replaces the old context."""
    ctx = ContextManager(system_prompt="Base prompt")
    ctx.update_session_context("## Session State\nTurn 1.")
    ctx.update_session_context("## Session State\nTurn 5. 10 tool calls.")

    assert "Turn 5" in ctx.system_prompt
    assert "Turn 1" not in ctx.system_prompt
    assert ctx.system_prompt.count("## Session State") == 1
