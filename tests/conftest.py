"""Shared test fixtures for Hauba."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_hauba_dir(tmp_path: Path) -> Path:
    """Create a temporary .hauba directory for testing."""
    hauba_dir = tmp_path / ".hauba"
    hauba_dir.mkdir()
    (hauba_dir / "agents").mkdir()
    (hauba_dir / "memory").mkdir()
    (hauba_dir / "skills").mkdir()
    (hauba_dir / "logs").mkdir()
    return hauba_dir


@pytest.fixture
def sample_task() -> dict:
    """A minimal task dict for testing."""
    return {
        "id": "test-task-001",
        "description": "Build a hello world app",
        "owner": "test-user",
    }


@pytest.fixture
def recorded_responses_dir() -> Path:
    """Path to recorded LLM responses for mocking."""
    return Path(__file__).parent / "fixtures" / "recorded_llm_responses"
