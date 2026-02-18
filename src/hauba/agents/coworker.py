"""CoWorker — Ephemeral helper agent that handles a single task and terminates."""

from __future__ import annotations

import structlog

from hauba.agents.base import BaseAgent
from hauba.brain.llm import LLMRouter
from hauba.core.config import ConfigManager
from hauba.core.events import EventEmitter
from hauba.core.types import (
    AgentState,
    LLMMessage,
    Plan,
    Result,
    TaskStep,
)

logger = structlog.get_logger()


class CoWorker(BaseAgent):
    """Ephemeral agent: single task, report result, terminate.

    Minimal LLM calls. No persistent state. No tools — pure LLM reasoning.
    Used for lightweight tasks like: summarize, classify, extract, format.
    """

    agent_type = "coworker"

    def __init__(
        self,
        config: ConfigManager,
        events: EventEmitter,
        task_description: str,
        parent_id: str = "",
    ) -> None:
        super().__init__(config, events)
        self.task_description = task_description
        self.parent_id = parent_id
        self._llm = LLMRouter(config)

    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """No deliberation — CoWorkers act immediately."""
        return Plan(
            task_id=task_id,
            understanding=instruction,
            approach="Direct LLM completion",
            steps=[TaskStep(id=f"{task_id}-cw", description=instruction)],
            confidence=0.9,
        )

    async def execute(self, plan: Plan) -> Result:
        """Execute via a single LLM call — no tools."""
        messages = [
            LLMMessage(
                role="system",
                content="You are a focused helper. Complete the task concisely. No tool calls needed.",
            ),
            LLMMessage(role="user", content=self.task_description),
        ]

        response = await self._llm.complete(messages, temperature=0.3)
        return Result.ok(response.content)

    async def review(self, result: Result) -> Result:
        """No review — ephemeral agents just return."""
        return result

    async def run(self, instruction: str) -> Result:
        """Override run to auto-terminate after execution."""
        result = await super().run(instruction)
        self.state = AgentState.TERMINATED
        return result
