"""Base agent — lifecycle management for all Hauba agents."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

import structlog

from hauba.core.config import ConfigManager
from hauba.core.constants import (
    EVENT_AGENT_EXECUTING,
    EVENT_AGENT_REVIEWING,
    EVENT_AGENT_THINKING,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_FAILED,
    EVENT_TASK_STARTED,
)
from hauba.core.events import EventEmitter
from hauba.core.types import AgentState, Plan, Result

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Base class for all Hauba agents."""

    agent_type: str = "base"

    def __init__(self, config: ConfigManager, events: EventEmitter) -> None:
        self.id = f"{self.agent_type}-{uuid.uuid4().hex[:8]}"
        self.config = config
        self.events = events
        self.state = AgentState.IDLE

    async def run(self, instruction: str) -> Result:
        """Full agent lifecycle: deliberate → execute → review."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        await self.events.emit(
            EVENT_TASK_STARTED,
            {
                "task_id": task_id,
                "agent_id": self.id,
                "instruction": instruction,
            },
            source=self.id,
            task_id=task_id,
        )

        try:
            # Phase 1: Deliberate
            self.state = AgentState.DELIBERATING
            await self.events.emit(
                EVENT_AGENT_THINKING,
                {
                    "agent_id": self.id,
                    "phase": "deliberating",
                },
                source=self.id,
                task_id=task_id,
            )

            plan = await self.deliberate(instruction, task_id)

            # Phase 2: Execute
            self.state = AgentState.EXECUTING
            await self.events.emit(
                EVENT_AGENT_EXECUTING,
                {
                    "agent_id": self.id,
                    "steps": len(plan.steps),
                },
                source=self.id,
                task_id=task_id,
            )

            result = await self.execute(plan)

            # Phase 3: Review
            self.state = AgentState.REVIEWING
            await self.events.emit(
                EVENT_AGENT_REVIEWING,
                {
                    "agent_id": self.id,
                },
                source=self.id,
                task_id=task_id,
            )

            final = await self.review(result)

            self.state = AgentState.COMPLETED
            await self.events.emit(
                EVENT_TASK_COMPLETED,
                {
                    "task_id": task_id,
                    "success": final.success,
                },
                source=self.id,
                task_id=task_id,
            )

            return final

        except Exception as exc:
            self.state = AgentState.FAILED
            await self.events.emit(
                EVENT_TASK_FAILED,
                {
                    "task_id": task_id,
                    "error": str(exc),
                },
                source=self.id,
                task_id=task_id,
            )
            logger.exception("agent.failed", agent_id=self.id, task_id=task_id)
            return Result.fail(str(exc))

    @abstractmethod
    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """Think before acting — produce a plan."""
        ...

    @abstractmethod
    async def execute(self, plan: Plan) -> Result:
        """Execute the plan step by step."""
        ...

    @abstractmethod
    async def review(self, result: Result) -> Result:
        """Review the execution result."""
        ...
