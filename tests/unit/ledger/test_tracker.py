"""Tests for TaskLedger — bit-vector + SHA-256 hash-chain tracker."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.exceptions import GateCheckError, LedgerError
from hauba.ledger.tracker import LedgerState, TaskLedger


@pytest.fixture
def ledger() -> TaskLedger:
    """Create a ledger with 3 tasks (A -> B -> C)."""
    ldg = TaskLedger("test-ledger")
    ldg.add_task("A", "First task")
    ldg.add_task("B", "Second task", dependencies=["A"])
    ldg.add_task("C", "Third task", dependencies=["B"])
    return ldg


def test_add_task_and_initial_state(ledger: TaskLedger) -> None:
    assert ledger.task_count == 3
    assert ledger.get_state("A") == LedgerState.NOT_STARTED
    assert ledger.get_state("B") == LedgerState.NOT_STARTED
    assert ledger.get_state("C") == LedgerState.NOT_STARTED


def test_add_duplicate_task_raises() -> None:
    ledger = TaskLedger("test")
    ledger.add_task("A", "Task A")
    with pytest.raises(LedgerError, match="already exists"):
        ledger.add_task("A", "Duplicate A")


def test_start_task_marks_in_progress(ledger: TaskLedger) -> None:
    ledger.start_task("A")
    assert ledger.get_state("A") == LedgerState.IN_PROGRESS


def test_start_task_dependency_gate(ledger: TaskLedger) -> None:
    """Gate 2: Cannot start B before A is VERIFIED."""
    with pytest.raises(GateCheckError, match="not verified"):
        ledger.start_task("B")


def test_complete_task_with_artifact(ledger: TaskLedger) -> None:
    """Gate 3: Completing a task hashes the artifact."""
    ledger.start_task("A")
    artifact_hash = ledger.complete_task("A", artifact="hello world")
    assert ledger.get_state("A") == LedgerState.VERIFIED
    assert len(artifact_hash) == 64  # SHA-256 hex


def test_complete_task_not_in_progress_raises(ledger: TaskLedger) -> None:
    with pytest.raises(LedgerError, match="not IN_PROGRESS"):
        ledger.complete_task("A")


def test_hash_chain_integrity(ledger: TaskLedger) -> None:
    """Verify hash chain links artifacts correctly."""
    ledger.start_task("A")
    ledger.complete_task("A", artifact="result-A")
    ledger.start_task("B")
    ledger.complete_task("B", artifact="result-B")
    ledger.start_task("C")
    ledger.complete_task("C", artifact="result-C")

    # Hash chain should be valid
    assert ledger._verify_hash_chain()


def test_get_ready_tasks(ledger: TaskLedger) -> None:
    """Only tasks with all deps satisfied are ready."""
    assert ledger.get_ready_tasks() == ["A"]

    ledger.start_task("A")
    assert ledger.get_ready_tasks() == []  # A is in_progress, not verified

    ledger.complete_task("A", artifact="done")
    assert ledger.get_ready_tasks() == ["B"]

    ledger.start_task("B")
    ledger.complete_task("B", artifact="done")
    assert ledger.get_ready_tasks() == ["C"]


def test_gate_check_all_verified(ledger: TaskLedger) -> None:
    """Gate 4: All tasks must be VERIFIED for gate_check to pass."""
    ledger.start_task("A")
    ledger.complete_task("A", artifact="a")
    ledger.start_task("B")
    ledger.complete_task("B", artifact="b")
    ledger.start_task("C")
    ledger.complete_task("C", artifact="c")

    assert ledger.gate_check() is True


def test_gate_check_incomplete_fails(ledger: TaskLedger) -> None:
    """Gate 4: Fails if any task is not VERIFIED."""
    ledger.start_task("A")
    ledger.complete_task("A", artifact="a")
    # B and C are still NOT_STARTED

    with pytest.raises(GateCheckError, match="not verified"):
        ledger.gate_check()


def test_reconciliation(ledger: TaskLedger) -> None:
    """Gate 5: Plan count must match ledger count."""
    assert ledger.reconcile(3) is True

    with pytest.raises(GateCheckError, match="Expected 5"):
        ledger.reconcile(5)


def test_from_plan() -> None:
    """Create ledger from plan steps."""
    steps = [
        {"id": "s1", "description": "Step 1"},
        {"id": "s2", "description": "Step 2", "dependencies": ["s1"]},
    ]
    ledger = TaskLedger.from_plan(steps, "plan-test")
    assert ledger.task_count == 2
    assert ledger.get_ready_tasks() == ["s1"]


def test_persist_and_load(tmp_path: Path) -> None:
    """Test round-trip persistence to JSON."""
    ledger = TaskLedger("persist-test", workspace=tmp_path)
    ledger.add_task("X", "Task X")
    ledger.start_task("X")
    ledger.complete_task("X", artifact="output")
    ledger.persist()

    assert (tmp_path / "ledger.json").exists()

    loaded = TaskLedger.load(tmp_path / "ledger.json")
    assert loaded.ledger_id == "persist-test"
    assert loaded.task_count == 1
    assert loaded.get_state("X") == LedgerState.VERIFIED


def test_generate_todo_md(ledger: TaskLedger) -> None:
    """Generate human-readable TODO markdown."""
    ledger.start_task("A")
    ledger.complete_task("A", artifact="done")

    todo = ledger.generate_todo_md()
    assert "test-ledger" in todo
    assert "[x]" in todo  # A is verified
    assert "[ ]" in todo  # C is not started
    assert "1/3" in todo  # Progress


def test_progress_properties(ledger: TaskLedger) -> None:
    assert ledger.progress == (0, 3)
    assert ledger.is_complete is False

    ledger.start_task("A")
    ledger.complete_task("A", artifact="a")
    assert ledger.verified_count == 1
    assert ledger.in_progress_count == 0

    ledger.start_task("B")
    assert ledger.in_progress_count == 1


def test_get_nonexistent_task_raises() -> None:
    ledger = TaskLedger("test")
    with pytest.raises(LedgerError, match="not found"):
        ledger.get_state("nonexistent")
