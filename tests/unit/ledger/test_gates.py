"""Tests for VerificationGates — all 5 anti-hallucination gates."""

from __future__ import annotations

import pytest

from hauba.exceptions import GateCheckError
from hauba.ledger.gates import VerificationGates
from hauba.ledger.tracker import TaskLedger


@pytest.fixture
def ledger_and_gates() -> tuple[TaskLedger, VerificationGates]:
    """Ledger with 2 tasks: A -> B."""
    ledger = TaskLedger("gate-test")
    ledger.add_task("A", "Task A")
    ledger.add_task("B", "Task B", dependencies=["A"])
    return ledger, VerificationGates(ledger)


def test_gate_1_pre_execution_passes(ledger_and_gates: tuple) -> None:
    _ledger, gates = ledger_and_gates
    assert gates.gate_1_pre_execution() is True


def test_gate_1_empty_ledger_fails() -> None:
    ledger = TaskLedger("empty")
    gates = VerificationGates(ledger)
    with pytest.raises(GateCheckError, match="Gate 1"):
        gates.gate_1_pre_execution()


def test_gate_2_dependency_check(ledger_and_gates: tuple) -> None:
    ledger, gates = ledger_and_gates
    # B depends on A — should fail before A is verified
    with pytest.raises(GateCheckError, match="Gate 2"):
        gates.gate_2_dependency("B")

    # After A is verified, B should pass
    ledger.start_task("A")
    ledger.complete_task("A", artifact="done")
    assert gates.gate_2_dependency("B") is True


def test_gate_3_completion_check(ledger_and_gates: tuple) -> None:
    ledger, gates = ledger_and_gates
    # A is NOT_STARTED — should fail
    with pytest.raises(GateCheckError, match="Gate 3"):
        gates.gate_3_completion("A")

    # After completing A, should pass
    ledger.start_task("A")
    ledger.complete_task("A", artifact="done")
    assert gates.gate_3_completion("A") is True


def test_gate_4_delivery(ledger_and_gates: tuple) -> None:
    ledger, gates = ledger_and_gates
    # Not all tasks verified yet
    with pytest.raises(GateCheckError, match="Gate 4"):
        gates.gate_4_delivery()

    # Complete all tasks
    ledger.start_task("A")
    ledger.complete_task("A", artifact="a")
    ledger.start_task("B")
    ledger.complete_task("B", artifact="b")
    assert gates.gate_4_delivery() is True


def test_gate_5_reconciliation(ledger_and_gates: tuple) -> None:
    _ledger, gates = ledger_and_gates
    assert gates.gate_5_reconciliation(2) is True

    with pytest.raises(GateCheckError, match="Gate 5"):
        gates.gate_5_reconciliation(10)


def test_full_verification(ledger_and_gates: tuple) -> None:
    ledger, gates = ledger_and_gates
    ledger.start_task("A")
    ledger.complete_task("A", artifact="a")
    ledger.start_task("B")
    ledger.complete_task("B", artifact="b")

    assert gates.full_verification(expected_count=2) is True


def test_full_verification_fails_incomplete(ledger_and_gates: tuple) -> None:
    _, gates = ledger_and_gates
    with pytest.raises(GateCheckError):
        gates.full_verification(expected_count=2)
