"""Tests for ReplayRecorder — JSON Lines event recording."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hauba.core.events import EventEmitter
from hauba.core.replay import ReplayRecorder
from hauba.core.types import Event, ReplayEntry


@pytest.fixture
def recorder(tmp_path: Path) -> ReplayRecorder:
    return ReplayRecorder(task_id="test-task", output_dir=tmp_path)


# --- Initialization ---


def test_recorder_creates_replay_file(tmp_path: Path) -> None:
    recorder = ReplayRecorder(task_id="init-test", output_dir=tmp_path)
    assert recorder.path.exists()
    assert recorder.path.name == ".hauba-replay"
    recorder.close()


def test_recorder_entry_count_starts_zero(recorder: ReplayRecorder) -> None:
    assert recorder.entry_count == 0
    recorder.close()


# --- Recording events ---


async def test_handle_event_writes_json_line(recorder: ReplayRecorder) -> None:
    event = Event(topic="task.started", data={"key": "value"}, source="agent-1", task_id="t1")
    await recorder.handle_event(event)
    recorder.close()

    lines = recorder.path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["topic"] == "task.started"
    assert parsed["data"]["key"] == "value"
    assert parsed["source"] == "agent-1"


async def test_handle_event_increments_count(recorder: ReplayRecorder) -> None:
    for i in range(5):
        event = Event(topic=f"event.{i}", data={"i": i})
        await recorder.handle_event(event)
    assert recorder.entry_count == 5
    recorder.close()


async def test_multiple_events_written_as_jsonl(recorder: ReplayRecorder) -> None:
    for i in range(3):
        event = Event(topic=f"tool.call.{i}", data={"step": i})
        await recorder.handle_event(event)
    recorder.close()

    lines = recorder.path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    for i, line in enumerate(lines):
        parsed = json.loads(line)
        assert parsed["topic"] == f"tool.call.{i}"


# --- Subscribe to EventEmitter ---


async def test_subscribe_captures_all_events(tmp_path: Path) -> None:
    events = EventEmitter()
    recorder = ReplayRecorder(task_id="sub-test", output_dir=tmp_path)
    recorder.subscribe(events)

    await events.emit("task.started", {"msg": "hello"})
    await events.emit("agent.thinking", {"phase": "deliberating"})
    await events.emit("tool.called", {"tool": "bash"})

    assert recorder.entry_count == 3
    recorder.close()

    entries = ReplayRecorder.load(recorder.path)
    assert len(entries) == 3
    assert entries[0].topic == "task.started"
    assert entries[1].topic == "agent.thinking"
    assert entries[2].topic == "tool.called"


# --- Load ---


async def test_load_returns_replay_entries(recorder: ReplayRecorder) -> None:
    event = Event(topic="ledger.gate_passed", data={"gate": 4}, source="dir-1", task_id="t-1")
    await recorder.handle_event(event)
    recorder.close()

    entries = ReplayRecorder.load(recorder.path)
    assert len(entries) == 1
    assert isinstance(entries[0], ReplayEntry)
    assert entries[0].topic == "ledger.gate_passed"
    assert entries[0].data["gate"] == 4


def test_load_empty_file(tmp_path: Path) -> None:
    replay_file = tmp_path / ".hauba-replay"
    replay_file.write_text("", encoding="utf-8")
    entries = ReplayRecorder.load(replay_file)
    assert entries == []


def test_load_skips_blank_lines(tmp_path: Path) -> None:
    replay_file = tmp_path / ".hauba-replay"
    entry = ReplayEntry(topic="a.b", data={"x": 1})
    replay_file.write_text(
        entry.model_dump_json() + "\n\n" + entry.model_dump_json() + "\n",
        encoding="utf-8",
    )
    entries = ReplayRecorder.load(replay_file)
    assert len(entries) == 2


# --- Close ---


def test_close_is_idempotent(recorder: ReplayRecorder) -> None:
    recorder.close()
    recorder.close()  # Should not raise
