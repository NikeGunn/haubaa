"""Verification Gates — Five anti-hallucination gates for TaskLedger.

Gate 1: PRE-EXECUTION — Ledger must exist before work begins
Gate 2: DEPENDENCY — All deps VERIFIED before task start
Gate 3: COMPLETION — Hash output, verify on disk
Gate 4: DELIVERY — Full ledger GateCheck at each level
Gate 5: RECONCILIATION — Plan count vs ledger count
"""

from __future__ import annotations

from pathlib import Path

import structlog

from hauba.exceptions import GateCheckError
from hauba.ledger.tracker import LedgerState, TaskLedger

logger = structlog.get_logger()


class VerificationGates:
    """Enforces all 5 anti-hallucination gates on a TaskLedger."""

    def __init__(self, ledger: TaskLedger) -> None:
        self._ledger = ledger

    def gate_1_pre_execution(self) -> bool:
        """Gate 1: Ledger must exist and have tasks before any work begins.

        Raises GateCheckError if ledger is empty.
        """
        if self._ledger.task_count == 0:
            raise GateCheckError(
                "Gate 1 FAILED: Ledger has no tasks — cannot begin execution"
            )
        logger.debug("gate.1_passed", ledger_id=self._ledger.ledger_id)
        return True

    def gate_2_dependency(self, task_id: str) -> bool:
        """Gate 2: All dependencies must be VERIFIED before task can start.

        This is enforced by TaskLedger.start_task() internally.
        This method provides an explicit pre-check.
        """
        idx = self._ledger._get_index(task_id)
        entry = self._ledger._tasks[idx]

        for dep_id in entry.dependencies:
            dep_state = self._ledger.get_state(dep_id)
            if dep_state != LedgerState.VERIFIED:
                raise GateCheckError(
                    f"Gate 2 FAILED: Dependency {dep_id} for task {task_id} "
                    f"not verified (state={dep_state.name})"
                )
        logger.debug("gate.2_passed", task_id=task_id)
        return True

    def gate_3_completion(self, task_id: str, artifact_path: Path | None = None) -> bool:
        """Gate 3: Task must be VERIFIED and artifact must exist on disk (if specified).

        Raises GateCheckError if task not verified or artifact missing.
        """
        state = self._ledger.get_state(task_id)
        if state != LedgerState.VERIFIED:
            raise GateCheckError(
                f"Gate 3 FAILED: Task {task_id} not verified (state={state.name})"
            )

        if artifact_path and not artifact_path.exists():
            raise GateCheckError(
                f"Gate 3 FAILED: Artifact for {task_id} not found at {artifact_path}"
            )

        logger.debug("gate.3_passed", task_id=task_id)
        return True

    def gate_4_delivery(self) -> bool:
        """Gate 4: Full delivery gate — all tasks verified, hash chain intact.

        Delegates to TaskLedger.gate_check().
        """
        return self._ledger.gate_check()

    def gate_5_reconciliation(self, expected_count: int) -> bool:
        """Gate 5: Plan count must match ledger count.

        Ensures no tasks were forgotten or fabricated.
        """
        return self._ledger.reconcile(expected_count)

    def full_verification(self, expected_count: int) -> bool:
        """Run all applicable gates for final delivery verification.

        Gates 1, 4, and 5 are checked. Gates 2 and 3 are per-task.
        """
        self.gate_1_pre_execution()
        self.gate_4_delivery()
        self.gate_5_reconciliation(expected_count)
        logger.info("gates.all_passed", ledger_id=self._ledger.ledger_id)
        return True
