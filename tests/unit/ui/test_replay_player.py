"""Tests for ReplayPlayer — Rich-based event playback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from hauba.core.types import ReplayEntry
from hauba.exceptions import ReplayError
from hauba.ui.replay import TOPIC_COLORS, ReplayPlayer


@pytest.fixture
def console() -> Console:
    return Console(file=StringIO(), width=120, color_system=None)


@pytest.fixture
def player(console: Console) -> ReplayPlayer:
    return ReplayPlayer(console=console)


def _write_entries(path: Path, entries: list[ReplayEntry]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(entry.model_dump_json() + "\n")


# --- Errors ---


async def test_play_missing_file_raises(player: ReplayPlayer, tmp_path: Path) -> None:
    with pytest.raises(ReplayError, match="not found"):
        await player.play(tmp_path / "nonexistent.replay")


# --- Empty replay ---


async def test_play_empty_file(player: ReplayPlayer, tmp_path: Path) -> None:
    replay_file = tmp_path / ".hauba-replay"
    replay_file.write_text("", encoding="utf-8")
    count = await player.play(replay_file)
    assert count == 0


# --- Normal playback ---


async def test_play_returns_entry_count(player: ReplayPlayer, tmp_path: Path) -> None:
    now = datetime.now(UTC)
    entries = [
        ReplayEntry(timestamp=now, topic="task.started", data={"msg": "go"}),
        ReplayEntry(timestamp=now + timedelta(seconds=0.1), topic="agent.thinking", data={}),
        ReplayEntry(timestamp=now + timedelta(seconds=0.2), topic="task.completed", data={}),
    ]
    replay_file = tmp_path / ".hauba-replay"
    _write_entries(replay_file, entries)

    count = await player.play(replay_file, speed=100.0)  # Fast speed for testing
    assert count == 3


async def test_play_renders_topics(player: ReplayPlayer, console: Console, tmp_path: Path) -> None:
    now = datetime.now(UTC)
    entries = [
        ReplayEntry(timestamp=now, topic="tool.called", data={"tool": "bash"}, source="worker-1"),
    ]
    replay_file = tmp_path / ".hauba-replay"
    _write_entries(replay_file, entries)

    await player.play(replay_file, speed=100.0)
    output = console.file.getvalue()
    assert "tool.called" in output
    assert "worker-1" in output


async def test_play_shows_data(player: ReplayPlayer, console: Console, tmp_path: Path) -> None:
    now = datetime.now(UTC)
    entries = [
        ReplayEntry(timestamp=now, topic="llm.response", data={"tokens": 150}),
    ]
    replay_file = tmp_path / ".hauba-replay"
    _write_entries(replay_file, entries)

    await player.play(replay_file, speed=100.0, show_data=True)
    output = console.file.getvalue()
    assert "tokens" in output
    assert "150" in output


async def test_play_hides_data_when_disabled(
    player: ReplayPlayer, console: Console, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    entries = [
        ReplayEntry(timestamp=now, topic="llm.response", data={"tokens": 150}),
    ]
    replay_file = tmp_path / ".hauba-replay"
    _write_entries(replay_file, entries)

    await player.play(replay_file, speed=100.0, show_data=False)
    output = console.file.getvalue()
    assert "llm.response" in output
    # Data keys should not appear
    assert "tokens: 150" not in output


# --- Topic color mapping ---


def test_topic_colors_cover_all_prefixes() -> None:
    expected = {
        "task",
        "agent",
        "llm",
        "tool",
        "browser",
        "screen",
        "replay",
        "ledger",
        "milestone",
    }
    assert expected.issubset(set(TOPIC_COLORS.keys()))


# --- Render entry ---


def test_render_entry_truncates_long_values(player: ReplayPlayer, console: Console) -> None:
    entry = ReplayEntry(
        topic="test.long",
        data={"big": "x" * 200},
        source="src",
    )
    player._render_entry(entry, show_data=True)
    output = console.file.getvalue()
    assert "..." in output
