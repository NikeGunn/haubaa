"""Task planner — decomposes instructions into dependency-aware step lists."""

from __future__ import annotations

import structlog

from hauba.core.types import Plan, TaskStatus, TaskStep

logger = structlog.get_logger()


class TaskPlanner:
    """Manages plan execution order respecting dependencies."""

    def __init__(self, plan: Plan) -> None:
        self._plan = plan
        self._step_map: dict[str, TaskStep] = {s.id: s for s in plan.steps}

    def get_ready_steps(self) -> list[TaskStep]:
        """Get steps whose dependencies are all VERIFIED."""
        ready = []
        for step in self._plan.steps:
            if step.status != TaskStatus.NOT_STARTED:
                continue
            deps_met = all(
                self._step_map[dep_id].status == TaskStatus.VERIFIED
                for dep_id in step.dependencies
                if dep_id in self._step_map
            )
            if deps_met:
                ready.append(step)
        return ready

    def mark_step(self, step_id: str, status: TaskStatus) -> None:
        """Update a step's status."""
        if step_id in self._step_map:
            self._step_map[step_id].status = status
            logger.info("planner.step_updated", step_id=step_id, status=status.value)

    def get_step_status(self, step_id: str) -> TaskStatus:
        """Get a step's current status."""
        step = self._step_map.get(step_id)
        return step.status if step else TaskStatus.NOT_STARTED

    def is_complete(self) -> bool:
        """Check if all steps are VERIFIED."""
        return all(s.status == TaskStatus.VERIFIED for s in self._plan.steps)

    def has_failures(self) -> bool:
        """Check if any step FAILED."""
        return any(s.status == TaskStatus.FAILED for s in self._plan.steps)

    @property
    def progress(self) -> tuple[int, int]:
        """Return (completed, total) count."""
        done = sum(1 for s in self._plan.steps if s.status == TaskStatus.VERIFIED)
        return done, len(self._plan.steps)
