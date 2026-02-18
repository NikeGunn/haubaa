"""Tests for Write-Ahead Log (WAL) — crash-safe state persistence."""

from __future__ import annotations

from pathlib import Path

from hauba.ledger.wal import (
    WAL_OP_ADD_TASK,
    WAL_OP_COMPLETE_TASK,
    WAL_OP_START_TASK,
    WriteAheadLog,
)


def test_append_and_replay(tmp_path: Path) -> None:
    wal = WriteAheadLog(tmp_path / "test.wal")
    wal.append(WAL_OP_ADD_TASK, "task-1", {"desc": "First task"})
    wal.append(WAL_OP_START_TASK, "task-1")
    wal.append(WAL_OP_COMPLETE_TASK, "task-1", {"hash": "abc123"})

    assert wal.entry_count == 3
    assert wal.sequence == 3


def test_persist_to_disk(tmp_path: Path) -> None:
    wal_path = tmp_path / "persist.wal"
    wal = WriteAheadLog(wal_path)
    wal.append(WAL_OP_ADD_TASK, "X", {"desc": "Task X"})
    assert wal_path.exists()

    # Reload from disk
    wal2 = WriteAheadLog(wal_path)
    assert wal2.entry_count == 1
    entries = wal2.replay_all()
    assert entries[0].task_id == "X"


def test_checkpoint_and_replay(tmp_path: Path) -> None:
    wal = WriteAheadLog(tmp_path / "cp.wal")
    wal.append(WAL_OP_ADD_TASK, "A", {})
    wal.append(WAL_OP_COMPLETE_TASK, "A", {})
    wal.checkpoint()
    wal.append(WAL_OP_ADD_TASK, "B", {})

    # Replay from checkpoint should only return B
    entries = wal.replay_from_checkpoint()
    assert len(entries) == 1
    assert entries[0].task_id == "B"


def test_compact(tmp_path: Path) -> None:
    wal = WriteAheadLog(tmp_path / "compact.wal")
    wal.append(WAL_OP_ADD_TASK, "old", {})
    wal.checkpoint()
    wal.append(WAL_OP_ADD_TASK, "new", {})

    wal.compact()
    assert wal.entry_count == 1
    entries = wal.replay_all()
    assert entries[0].task_id == "new"


def test_empty_wal(tmp_path: Path) -> None:
    wal = WriteAheadLog(tmp_path / "empty.wal")
    assert wal.entry_count == 0
    assert wal.replay_all() == []
    assert wal.replay_from_checkpoint() == []
