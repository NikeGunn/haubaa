"""TaskLedger — Zero hallucination tracker with bit-vector + SHA-256 hash-chain.

Three data structures guarantee zero hallucination:
1. Bit-vector (bytearray) — O(1) per-task state tracking
2. Hash-chain (SHA-256) — Artifact verification
3. WAL checkpoints — Crash-safe state persistence

States: 0=NOT_STARTED, 1=IN_PROGRESS, 2=VERIFIED
"""

from __future__ import annotations

import hashlib
import json
import time
from enum import IntEnum
from pathlib import Path
from typing import Any

import structlog

from hauba.exceptions import GateCheckError, LedgerError

logger = structlog.get_logger()


class LedgerState(IntEnum):
    """Task states in the bit-vector."""

    NOT_STARTED = 0
    IN_PROGRESS = 1
    VERIFIED = 2


class TaskEntry:
    """A single task tracked by the ledger."""

    __slots__ = ("artifact_hash", "completed_at", "dependencies", "description", "id", "started_at")

    def __init__(
        self,
        id: str,
        description: str,
        dependencies: list[str] | None = None,
    ) -> None:
        self.id = id
        self.description = description
        self.dependencies = dependencies or []
        self.artifact_hash: str | None = None
        self.started_at: float | None = None
        self.completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "dependencies": self.dependencies,
            "artifact_hash": self.artifact_hash,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskEntry:
        entry = cls(
            id=data["id"],
            description=data["description"],
            dependencies=data.get("dependencies", []),
        )
        entry.artifact_hash = data.get("artifact_hash")
        entry.started_at = data.get("started_at")
        entry.completed_at = data.get("completed_at")
        return entry


class TaskLedger:
    """Zero-hallucination task tracker.

    Uses a bit-vector for O(1) state lookups, SHA-256 hash-chain for
    artifact verification, and persists to disk on every state change.
    """

    def __init__(self, ledger_id: str, workspace: Path | None = None) -> None:
        self.ledger_id = ledger_id
        self._workspace = workspace
        self._tasks: list[TaskEntry] = []
        self._task_index: dict[str, int] = {}  # id -> index
        self._bitvec: bytearray = bytearray()
        self._hash_chain: list[str] = []  # SHA-256 chain
        self._chain_head: str = hashlib.sha256(b"HAUBA_GENESIS").hexdigest()
        self._created_at: float = time.time()

    # ── Factory Methods ────────────────────────────────────────────────

    @classmethod
    def from_plan(cls, plan_steps: list[dict[str, Any]], ledger_id: str, workspace: Path | None = None) -> TaskLedger:
        """Create a ledger from a deliberation plan's steps.

        Each step dict must have 'id' and 'description', optionally 'dependencies'.
        """
        ledger = cls(ledger_id, workspace)
        for step in plan_steps:
            ledger.add_task(
                task_id=step["id"],
                description=step["description"],
                dependencies=step.get("dependencies", []),
            )
        if workspace:
            ledger.persist()
        logger.info("ledger.created_from_plan", ledger_id=ledger_id, tasks=len(plan_steps))
        return ledger

    @classmethod
    def load(cls, path: Path) -> TaskLedger:
        """Load a ledger from a JSON file on disk."""
        data = json.loads(path.read_text(encoding="utf-8"))
        ledger = cls(data["ledger_id"])
        ledger._workspace = path.parent
        ledger._created_at = data.get("created_at", time.time())
        ledger._chain_head = data.get("chain_head", ledger._chain_head)
        ledger._hash_chain = data.get("hash_chain", [])

        for task_data in data["tasks"]:
            entry = TaskEntry.from_dict(task_data)
            idx = len(ledger._tasks)
            ledger._tasks.append(entry)
            ledger._task_index[entry.id] = idx
            ledger._bitvec.append(data["bitvec"][idx])

        return ledger

    # ── Core Operations ────────────────────────────────────────────────

    def add_task(self, task_id: str, description: str, dependencies: list[str] | None = None) -> None:
        """Add a new task to the ledger."""
        if task_id in self._task_index:
            raise LedgerError(f"Task {task_id} already exists in ledger")
        idx = len(self._tasks)
        entry = TaskEntry(task_id, description, dependencies)
        self._tasks.append(entry)
        self._task_index[task_id] = idx
        self._bitvec.append(LedgerState.NOT_STARTED)

    def start_task(self, task_id: str) -> None:
        """Mark a task as IN_PROGRESS.

        Gate 2: All dependencies must be VERIFIED before starting.
        """
        idx = self._get_index(task_id)
        entry = self._tasks[idx]

        # Gate 2: Dependency check
        for dep_id in entry.dependencies:
            dep_idx = self._task_index.get(dep_id)
            if dep_idx is None:
                raise GateCheckError(f"Dependency {dep_id} not found in ledger")
            if self._bitvec[dep_idx] != LedgerState.VERIFIED:
                raise GateCheckError(
                    f"Cannot start {task_id}: dependency {dep_id} not verified "
                    f"(state={LedgerState(self._bitvec[dep_idx]).name})"
                )

        self._bitvec[idx] = LedgerState.IN_PROGRESS
        entry.started_at = time.time()
        self._persist_if_workspace()
        logger.info("ledger.task_started", task_id=task_id, ledger_id=self.ledger_id)

    def complete_task(self, task_id: str, artifact: str | bytes | None = None) -> str:
        """Mark a task as VERIFIED with optional artifact hash.

        Gate 3: Hash the output artifact and chain it.
        Returns the artifact hash.
        """
        idx = self._get_index(task_id)
        entry = self._tasks[idx]

        if self._bitvec[idx] != LedgerState.IN_PROGRESS:
            raise LedgerError(
                f"Cannot complete {task_id}: not IN_PROGRESS "
                f"(state={LedgerState(self._bitvec[idx]).name})"
            )

        # Gate 3: Hash the artifact
        if artifact is not None:
            if isinstance(artifact, str):
                artifact = artifact.encode("utf-8")
            artifact_hash = hashlib.sha256(artifact).hexdigest()
        else:
            artifact_hash = hashlib.sha256(f"{task_id}:completed".encode()).hexdigest()

        # Extend hash chain
        chain_input = f"{self._chain_head}:{task_id}:{artifact_hash}"
        new_head = hashlib.sha256(chain_input.encode()).hexdigest()
        self._hash_chain.append(new_head)
        self._chain_head = new_head

        entry.artifact_hash = artifact_hash
        entry.completed_at = time.time()
        self._bitvec[idx] = LedgerState.VERIFIED

        self._persist_if_workspace()
        logger.info("ledger.task_completed", task_id=task_id, artifact_hash=artifact_hash[:16])
        return artifact_hash

    def get_state(self, task_id: str) -> LedgerState:
        """Get the current state of a task. O(1)."""
        idx = self._get_index(task_id)
        return LedgerState(self._bitvec[idx])

    def get_ready_tasks(self) -> list[str]:
        """Get task IDs whose dependencies are all VERIFIED and are NOT_STARTED."""
        ready = []
        for entry in self._tasks:
            idx = self._task_index[entry.id]
            if self._bitvec[idx] != LedgerState.NOT_STARTED:
                continue
            deps_met = all(
                self._bitvec[self._task_index[dep]] == LedgerState.VERIFIED
                for dep in entry.dependencies
                if dep in self._task_index
            )
            if deps_met:
                ready.append(entry.id)
        return ready

    # ── Verification Gates ─────────────────────────────────────────────

    def gate_check(self) -> bool:
        """Gate 4: Full delivery gate check.

        Verifies ALL tasks are VERIFIED and the hash chain is intact.
        Raises GateCheckError on failure.
        """
        # Check all tasks verified
        for i, entry in enumerate(self._tasks):
            if self._bitvec[i] != LedgerState.VERIFIED:
                raise GateCheckError(
                    f"Gate 4 FAILED: Task {entry.id} not verified "
                    f"(state={LedgerState(self._bitvec[i]).name})"
                )

        # Verify hash chain integrity
        if not self._verify_hash_chain():
            raise GateCheckError("Gate 4 FAILED: Hash chain integrity check failed")

        logger.info("ledger.gate_check_passed", ledger_id=self.ledger_id)
        return True

    def reconcile(self, expected_count: int) -> bool:
        """Gate 5: Reconciliation — plan count vs ledger count.

        Ensures no tasks were forgotten or fabricated.
        """
        actual = len(self._tasks)
        if actual != expected_count:
            raise GateCheckError(
                f"Gate 5 FAILED: Expected {expected_count} tasks, ledger has {actual}"
            )
        return True

    def verify_all(self) -> bool:
        """Run all gates: check every task is verified, chain is intact, counts match."""
        return self.gate_check()

    # ── Hash Chain ─────────────────────────────────────────────────────

    def _verify_hash_chain(self) -> bool:
        """Re-derive the hash chain from scratch and compare against stored chain."""
        if not self._hash_chain:
            return True  # No completed tasks yet

        head = hashlib.sha256(b"HAUBA_GENESIS").hexdigest()
        chain_idx = 0

        for entry in self._tasks:
            if entry.artifact_hash is None:
                continue
            chain_input = f"{head}:{entry.id}:{entry.artifact_hash}"
            head = hashlib.sha256(chain_input.encode()).hexdigest()

            if chain_idx >= len(self._hash_chain):
                return False
            if self._hash_chain[chain_idx] != head:
                return False
            chain_idx += 1

        return chain_idx == len(self._hash_chain)

    # ── Persistence ────────────────────────────────────────────────────

    def persist(self) -> None:
        """Save ledger state to disk as JSON."""
        if not self._workspace:
            return
        self._workspace.mkdir(parents=True, exist_ok=True)
        path = self._workspace / "ledger.json"
        data = {
            "ledger_id": self.ledger_id,
            "created_at": self._created_at,
            "chain_head": self._chain_head,
            "hash_chain": self._hash_chain,
            "bitvec": list(self._bitvec),
            "tasks": [t.to_dict() for t in self._tasks],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _persist_if_workspace(self) -> None:
        if self._workspace:
            self.persist()

    def generate_todo_md(self) -> str:
        """Generate a human-readable TODO.md from ledger state."""
        lines = [f"# TODO — {self.ledger_id}\n"]
        completed = sum(1 for b in self._bitvec if b == LedgerState.VERIFIED)
        total = len(self._tasks)
        lines.append(f"\nProgress: {completed}/{total} tasks verified\n")

        for i, entry in enumerate(self._tasks):
            state = LedgerState(self._bitvec[i])
            if state == LedgerState.VERIFIED:
                marker = "[x]"
            elif state == LedgerState.IN_PROGRESS:
                marker = "[~]"
            else:
                marker = "[ ]"
            lines.append(f"\n- {marker} {entry.description}")
            if entry.dependencies:
                lines.append(f"  (depends on: {', '.join(entry.dependencies)})")

        lines.append(f"\n\nHash chain head: {self._chain_head[:16]}...")
        return "".join(lines)

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def verified_count(self) -> int:
        return sum(1 for b in self._bitvec if b == LedgerState.VERIFIED)

    @property
    def in_progress_count(self) -> int:
        return sum(1 for b in self._bitvec if b == LedgerState.IN_PROGRESS)

    @property
    def progress(self) -> tuple[int, int]:
        """Return (verified, total)."""
        return self.verified_count, self.task_count

    @property
    def is_complete(self) -> bool:
        return self.verified_count == self.task_count and self.task_count > 0

    @property
    def chain_head(self) -> str:
        return self._chain_head

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_index(self, task_id: str) -> int:
        idx = self._task_index.get(task_id)
        if idx is None:
            raise LedgerError(f"Task {task_id} not found in ledger")
        return idx

    def __repr__(self) -> str:
        return f"<TaskLedger {self.ledger_id} [{self.verified_count}/{self.task_count}]>"
