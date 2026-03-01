"""Tests for CopilotEngine interactive features — plan state, multi-turn, user input, delivery."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.engine.copilot_engine import CopilotEngine, PlanState
from hauba.engine.types import EngineConfig, EngineResult, ProviderType

# --- PlanState tests ---


def test_plan_state_save_load(tmp_path: Path) -> None:
    """PlanState can be saved to disk and loaded back."""
    state = PlanState(
        task="Build a REST API",
        plan_text="1. Create FastAPI app\n2. Add endpoints",
        approved=True,
        session_id="test-session-123",
        timestamp=1234567890.0,
        workspace="/tmp/hauba-output",
        files_created=["main.py", "requirements.txt"],
    )

    plan_path = tmp_path / "plan.json"
    state.save(plan_path)

    assert plan_path.exists()

    loaded = PlanState.load(plan_path)
    assert loaded is not None
    assert loaded.task == "Build a REST API"
    assert loaded.approved is True
    assert loaded.session_id == "test-session-123"
    assert loaded.files_created == ["main.py", "requirements.txt"]
    assert loaded.plan_text == "1. Create FastAPI app\n2. Add endpoints"


def test_plan_state_load_nonexistent(tmp_path: Path) -> None:
    """Loading from a nonexistent path returns None."""
    result = PlanState.load(tmp_path / "nonexistent.json")
    assert result is None


def test_plan_state_load_invalid_json(tmp_path: Path) -> None:
    """Loading invalid JSON returns None."""
    plan_path = tmp_path / "bad.json"
    plan_path.write_text("not json!!!", encoding="utf-8")
    result = PlanState.load(plan_path)
    assert result is None


def test_plan_state_defaults() -> None:
    """PlanState has sensible defaults."""
    state = PlanState()
    assert state.task == ""
    assert state.plan_text == ""
    assert state.approved is False
    assert state.session_id == ""
    assert state.files_created == []


# --- Engine interactive handler wiring tests ---


def test_set_user_input_handler() -> None:
    """User input handler can be set and is stored."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)

    async def handler(q: str, c: list[str], f: bool) -> str:
        return "test"

    engine.set_user_input_handler(handler)
    assert engine._user_input_handler is handler


def test_set_plan_review_handler() -> None:
    """Plan review handler can be set and is stored."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)

    async def handler(plan: str) -> bool:
        return True

    engine.set_plan_review_handler(handler)
    assert engine._plan_review_handler is handler


def test_set_delivery_handler() -> None:
    """Delivery handler can be set and is stored."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)

    async def handler(output: str, sid: str) -> None:
        pass

    engine.set_delivery_handler(handler)
    assert engine._delivery_handler is handler


def test_engine_session_initially_none() -> None:
    """Engine session is None before execute()."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    assert engine.session is None


def test_engine_plan_state_initially_none() -> None:
    """Engine plan_state is None before execute()."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    assert engine.plan_state is None


# --- System prompt now includes human escalation instructions ---


def test_system_prompt_includes_human_escalation() -> None:
    """System prompt tells agent to use ask_user for human escalation."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    prompt = engine._build_hauba_system_prompt()
    assert "HUMAN ESCALATION" in prompt
    assert "ask_user" in prompt
    assert "API key" in prompt
    assert "credentials" in prompt


# --- Session config includes on_user_input_request when handler is set ---


def test_session_config_includes_user_input_handler() -> None:
    """Session config includes on_user_input_request when handler is set."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)

    async def handler(q: str, c: list[str], f: bool) -> str:
        return "answer"

    engine.set_user_input_handler(handler)
    session_config = engine._build_session_config()
    assert "on_user_input_request" in session_config


def test_session_config_no_user_input_handler_when_not_set() -> None:
    """Session config does NOT include on_user_input_request when no handler."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    session_config = engine._build_session_config()
    assert "on_user_input_request" not in session_config


# --- send_message returns error when no session ---


@pytest.mark.asyncio
async def test_send_message_no_session() -> None:
    """send_message() returns error when no session exists."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    result = await engine.send_message("hello")
    assert not result.success
    assert "No active session" in (result.error or "")


# --- EngineResult tests ---


def test_engine_result_ok() -> None:
    """EngineResult.ok() creates a success result."""
    r = EngineResult.ok(output="done", session_id="s123")
    assert r.success is True
    assert r.output == "done"
    assert r.session_id == "s123"


def test_engine_result_fail() -> None:
    """EngineResult.fail() creates a failure result."""
    r = EngineResult.fail("something broke")
    assert r.success is False
    assert r.error == "something broke"
