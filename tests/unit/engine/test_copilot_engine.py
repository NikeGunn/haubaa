"""Tests for CopilotEngine — skill injection, configuration, and availability."""

from __future__ import annotations

from hauba.engine.copilot_engine import CopilotEngine
from hauba.engine.types import EngineConfig, ProviderType


def test_build_system_prompt_contains_protocol() -> None:
    """Default system prompt contains the execution protocol."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    prompt = engine._build_hauba_system_prompt()
    assert "EXECUTION PROTOCOL" in prompt
    assert "Phase 1: UNDERSTAND" in prompt
    assert "Phase 3: IMPLEMENT" in prompt
    assert "Phase 4: VERIFY" in prompt


def test_build_system_prompt_with_skill_context() -> None:
    """Skill context is appended to the system prompt."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config, skill_context="## Test Skill\n- Build REST APIs")
    prompt = engine._build_hauba_system_prompt()
    assert "## Test Skill" in prompt
    assert "- Build REST APIs" in prompt


def test_build_system_prompt_without_skill_context() -> None:
    """Without skill context, the prompt is still valid."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config, skill_context="")
    prompt = engine._build_hauba_system_prompt()
    assert "Hauba AI Workstation" in prompt
    assert "## Test Skill" not in prompt


def test_engine_is_available_checks_import() -> None:
    """Engine reports availability based on copilot SDK import."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    # Returns bool (True if SDK installed, False otherwise)
    assert isinstance(engine.is_available, bool)


def test_system_prompt_enforces_tool_use() -> None:
    """System prompt tells the agent to USE tools, not just describe."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    prompt = engine._build_hauba_system_prompt()
    assert "MUST use your tools" in prompt
    assert "no placeholders" in prompt.lower() or "no TODOs" in prompt
