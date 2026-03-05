"""Tests for CopilotEngine — skill injection, configuration, custom tools, and availability."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hauba.engine.copilot_engine import CopilotEngine, PlanState
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


def test_system_prompt_mentions_custom_tools() -> None:
    """System prompt mentions Hauba's custom web tools."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    prompt = engine._build_hauba_system_prompt()
    assert "hauba_web_search" in prompt
    assert "hauba_web_fetch" in prompt
    assert "hauba_browser" in prompt
    assert "hauba_send_email" in prompt


def test_system_prompt_mentions_desktop_apps() -> None:
    """System prompt mentions desktop application control."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    prompt = engine._build_hauba_system_prompt()
    assert "Blender" in prompt
    assert "FFmpeg" in prompt


def test_custom_tools_built_with_copilot_sdk() -> None:
    """Custom tools are built when Copilot SDK is available."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)

    # Mock the copilot module
    mock_tool = MagicMock()
    with patch.dict("sys.modules", {"copilot": MagicMock(Tool=mock_tool)}):
        tools = engine._build_custom_tools()
        assert len(tools) == 4  # web_search, web_fetch, browser, send_email


def test_custom_tools_empty_without_sdk() -> None:
    """Custom tools returns empty when Copilot SDK not installed."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)

    with patch.dict("sys.modules", {"copilot": None}):
        with patch("builtins.__import__", side_effect=ImportError("no copilot")):
            tools = engine._build_custom_tools()
            assert tools == []


def test_browser_tool_initialized_in_init() -> None:
    """Browser tool attribute is initialized to None."""
    config = EngineConfig(provider=ProviderType.ANTHROPIC, api_key="test")
    engine = CopilotEngine(config)
    assert engine._browser_tool is None


def test_plan_state_save_load(tmp_path: MagicMock) -> None:
    """Plan state can be saved and loaded."""
    state = PlanState(
        task="build a dashboard",
        plan_text="1. Create HTML\n2. Add CSS",
        approved=True,
        session_id="test-session",
        timestamp=1234567890.0,
        workspace="/tmp/test",
        files_created=["index.html", "style.css"],
    )

    path = tmp_path / "plan.json"
    state.save(path)
    assert path.exists()

    loaded = PlanState.load(path)
    assert loaded is not None
    assert loaded.task == "build a dashboard"
    assert loaded.approved is True
    assert loaded.files_created == ["index.html", "style.css"]


def test_plan_state_load_nonexistent() -> None:
    """Loading a nonexistent plan returns None."""
    from pathlib import Path

    result = PlanState.load(Path("/nonexistent/plan.json"))
    assert result is None
