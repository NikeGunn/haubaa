"""DAG Executor — Parallel milestone execution with WAIT architecture.

Parses milestone dependency graphs, finds "ready" milestones (all deps satisfied),
spawns parallel SubAgents, blocks dependent milestones until predecessors complete.
"""

from __future__ import annotations

import asyncio

import structlog

from hauba.agents.subagent import SubAgent
from hauba.core.config import ConfigManager
from hauba.core.events import EventEmitter
from hauba.core.types import Milestone, Result, TaskStatus
from hauba.ledger.tracker import TaskLedger

logger = structlog.get_logger()


class DAGExecutor:
    """Executes a DAG of milestones with parallel-where-safe, sequential-where-dependent.

    Uses the WAIT architecture: dependent milestones WAIT.
    Independent milestones run in PARALLEL.
    """

    def __init__(
        self,
        config: ConfigManager,
        events: EventEmitter,
        ledger: TaskLedger | None = None,
    ) -> None:
        self._config = config
        self._events = events
        self._ledger = ledger
        self._milestones: dict[str, Milestone] = {}
        self._results: dict[str, Result] = {}
        self._completion_events: dict[str, asyncio.Event] = {}

    def add_milestone(self, milestone: Milestone) -> None:
        """Add a milestone to the DAG."""
        self._milestones[milestone.id] = milestone
        self._completion_events[milestone.id] = asyncio.Event()

    def add_milestones(self, milestones: list[Milestone]) -> None:
        """Add multiple milestones."""
        for m in milestones:
            self.add_milestone(m)

    def get_ready_milestones(self) -> list[Milestone]:
        """Find milestones whose dependencies are all satisfied."""
        ready = []
        for milestone in self._milestones.values():
            if milestone.status != TaskStatus.NOT_STARTED:
                continue
            deps_met = all(
                self._milestones[dep].status == TaskStatus.VERIFIED
                for dep in milestone.dependencies
                if dep in self._milestones
            )
            if deps_met:
                ready.append(milestone)
        return ready

    async def execute(self) -> Result:
        """Execute the full DAG, respecting dependencies.

        Algorithm:
        1. Find all ready milestones (no unsatisfied deps)
        2. Spawn SubAgents for each, run in parallel
        3. When a milestone completes, re-check for newly ready milestones
        4. Repeat until all milestones are done or a failure halts execution
        """
        if not self._milestones:
            return Result.ok("No milestones to execute")

        logger.info("dag.execution_started", milestones=len(self._milestones))

        while True:
            ready = self.get_ready_milestones()
            if not ready:
                # Check if we're done or deadlocked
                all_done = all(
                    m.status in (TaskStatus.VERIFIED, TaskStatus.FAILED)
                    for m in self._milestones.values()
                )
                if all_done:
                    break
                # Deadlock — dependencies can never be satisfied
                not_started = [
                    m.id for m in self._milestones.values()
                    if m.status == TaskStatus.NOT_STARTED
                ]
                if not_started:
                    logger.error("dag.deadlock", blocked=not_started)
                    return Result.fail(
                        f"DAG deadlock: milestones {not_started} have unsatisfied dependencies"
                    )
                break

            # Run all ready milestones in parallel
            tasks = [self._execute_milestone(m) for m in ready]
            await asyncio.gather(*tasks)

        # Summarize results
        successes = sum(1 for m in self._milestones.values() if m.status == TaskStatus.VERIFIED)
        total = len(self._milestones)
        summary_parts = []
        for m in self._milestones.values():
            status = "OK" if m.status == TaskStatus.VERIFIED else "FAIL"
            result = self._results.get(m.id)
            detail = (result.value or result.error or "")[:100] if result else ""
            summary_parts.append(f"[{status}] {m.description}: {detail}")

        summary = "\n".join(summary_parts)
        success = successes == total

        logger.info("dag.execution_complete", success=success, completed=successes, total=total)
        return Result.ok(summary) if success else Result.fail(summary)

    async def _execute_milestone(self, milestone: Milestone) -> None:
        """Execute a single milestone via a SubAgent."""
        milestone.status = TaskStatus.IN_PROGRESS

        if self._ledger:
            try:
                self._ledger.start_task(milestone.id)
            except Exception as exc:
                logger.warning("dag.ledger_start_error", error=str(exc))

        subagent = SubAgent(
            config=self._config,
            events=self._events,
            milestone=milestone,
            ledger=self._ledger,
        )

        try:
            result = await subagent.run(milestone.description)
            self._results[milestone.id] = result

            if result.success:
                milestone.status = TaskStatus.VERIFIED
                if self._ledger:
                    self._ledger.complete_task(milestone.id, artifact=result.value or "")
            else:
                milestone.status = TaskStatus.FAILED

        except Exception as exc:
            logger.exception("dag.milestone_failed", milestone_id=milestone.id)
            milestone.status = TaskStatus.FAILED
            self._results[milestone.id] = Result.fail(str(exc))

        # Signal completion for any waiting dependents
        self._completion_events[milestone.id].set()

    @property
    def progress(self) -> tuple[int, int]:
        """Return (completed, total) milestone count."""
        done = sum(1 for m in self._milestones.values() if m.status == TaskStatus.VERIFIED)
        return done, len(self._milestones)

    def validate_dag(self) -> bool:
        """Check for cycles in the dependency graph using DFS."""
        visited: set[str] = set()
        in_stack: set[str] = set()

        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            in_stack.add(node_id)
            milestone = self._milestones.get(node_id)
            if milestone:
                for dep in milestone.dependencies:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in in_stack:
                        return True
            in_stack.discard(node_id)
            return False

        for mid in self._milestones:
            if mid not in visited:
                if has_cycle(mid):
                    logger.error("dag.cycle_detected")
                    return False
        return True
