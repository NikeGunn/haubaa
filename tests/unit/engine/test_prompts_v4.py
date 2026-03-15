"""Tests for V4 system prompts — minimal, effective."""

from __future__ import annotations

from hauba.engine.prompts import build_system_prompt


def test_build_system_prompt_basic() -> None:
    """System prompt is built with default content."""
    prompt = build_system_prompt()
    assert "Hauba" in prompt
    assert "tools" in prompt.lower()
    assert "Think first" in prompt


def test_build_system_prompt_with_tools() -> None:
    """System prompt includes tool names."""
    prompt = build_system_prompt(tool_names=["bash", "read_file", "write_file"])
    assert "bash" in prompt
    assert "read_file" in prompt
    assert "write_file" in prompt


def test_build_system_prompt_with_skill_context() -> None:
    """Skill context is appended to prompt."""
    prompt = build_system_prompt(
        skill_context="## REST API Design\n- Use RESTful conventions"
    )
    assert "REST API Design" in prompt
    assert "RESTful conventions" in prompt


def test_build_system_prompt_without_skill_context() -> None:
    """Without skill context, no skill section."""
    prompt = build_system_prompt(skill_context="")
    assert "Skill Guidance" not in prompt


def test_build_system_prompt_is_concise() -> None:
    """System prompt is reasonably short (~1000 tokens ≈ ~4000 chars)."""
    prompt = build_system_prompt(
        tool_names=["bash", "read_file", "write_file", "edit_file"]
    )
    # Should be under 3000 chars without skill context
    assert len(prompt) < 3000


def test_build_system_prompt_mentions_key_tools() -> None:
    """System prompt references important tool usage patterns."""
    prompt = build_system_prompt()
    assert "bash" in prompt.lower()
    assert "read_file" in prompt.lower()
    assert "edit_file" in prompt.lower()
    assert "write_file" in prompt.lower()
    assert "grep" in prompt.lower()


def test_build_system_prompt_no_stubs() -> None:
    """System prompt tells agent to write complete code."""
    prompt = build_system_prompt()
    assert "stubs" in prompt.lower() or "no stubs" in prompt.lower()
    assert "placeholders" in prompt.lower() or "no placeholders" in prompt.lower()


def test_build_system_prompt_mentions_verification() -> None:
    """System prompt tells agent to verify work."""
    prompt = build_system_prompt()
    assert "verify" in prompt.lower() or "test" in prompt.lower()
