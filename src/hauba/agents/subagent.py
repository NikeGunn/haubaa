"""SubAgent — Team Lead that receives milestones, spawns Workers, waits for results.

Phase 2: Cross-agent event sharing, TaskLedger-aware worker coordination.
"""

from __future__ import annotations

import asyncio

import structlog

from hauba.agents.base import BaseAgent
from hauba.agents.worker import Worker
from hauba.brain.llm import LLMRouter
from hauba.core.config import ConfigManager
from hauba.core.constants import (
    DEFAULT_MAX_PARALLEL_WORKERS,
    EVENT_FINDING_SHARED,
    EVENT_MILESTONE_COMPLETED,
    EVENT_MILESTONE_FAILED,
    EVENT_MILESTONE_STARTED,
)
from hauba.core.events import EventEmitter
from hauba.core.types import (
    AgentState,
    Event,
    LLMMessage,
    Milestone,
    Plan,
    Result,
)
from hauba.ledger.tracker import TaskLedger

logger = structlog.get_logger()

SUBAGENT_SYSTEM_PROMPT = """You are a SubAgent (Team Lead) in the Hauba AI engineering framework.
You receive a milestone from the Director and must decompose it into parallel sub-tasks for Workers.

For each sub-task, specify:
TASK: <description>
TOOL: <bash|files|git|none>

List all tasks. Independent tasks will run in parallel. Dependent tasks run sequentially.
"""


class SubAgent(BaseAgent):
    """SubAgent — receives a milestone, decomposes into tasks, spawns Workers."""

    agent_type = "subagent"

    def __init__(
        self,
        config: ConfigManager,
        events: EventEmitter,
        milestone: Milestone,
        ledger: TaskLedger | None = None,
    ) -> None:
        super().__init__(config, events)
        self.milestone = milestone
        self._llm = LLMRouter(config)
        self._ledger = ledger
        self._workers: list[Worker] = []
        self._max_parallel = DEFAULT_MAX_PARALLEL_WORKERS
        self._shared_findings: list[dict] = []

        # Listen for cross-agent findings
        self.events.on(EVENT_FINDING_SHARED, self._handle_finding)

    async def _handle_finding(self, event: Event) -> None:
        """Receive findings shared by other SubAgents."""
        if event.source != self.id:
            self._shared_findings.append(event.data)
            logger.debug("subagent.finding_received", from_agent=event.source)

    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """Mini-deliberation: decompose milestone into worker tasks."""
        context = f"Milestone: {instruction}"
        if self._shared_findings:
            context += "\n\nContext from other teams:\n"
            for finding in self._shared_findings:
                context += f"- {finding}\n"

        messages = [
            LLMMessage(role="system", content=SUBAGENT_SYSTEM_PROMPT),
            LLMMessage(role="user", content=context),
        ]
        response = await self._llm.complete(messages, temperature=0.3)

        # Parse tasks from response
        steps = []
        step_count = 0
        for line in response.content.split("\n"):
            stripped = line.strip()
            if stripped.upper().startswith("TASK:"):
                step_count += 1
                desc = stripped[5:].strip()
                tool = None
                steps.append({
                    "id": f"{task_id}-worker-{step_count}",
                    "description": desc,
                    "tool": tool,
                })

        # If LLM didn't provide structured tasks, use milestone's pre-defined tasks
        if not steps and self.milestone.tasks:
            for task_step in self.milestone.tasks:
                steps.append({
                    "id": task_step.id,
                    "description": task_step.description,
                    "tool": task_step.tool,
                })

        from hauba.core.types import TaskStep

        plan = Plan(
            task_id=task_id,
            understanding=f"Milestone: {self.milestone.description}",
            approach="Decompose into parallel worker tasks",
            steps=[
                TaskStep(
                    id=s["id"],
                    description=s["description"],
                    tool=s.get("tool"),
                )
                for s in steps
            ],
            confidence=0.8,
        )
        return plan

    async def execute(self, plan: Plan) -> Result:
        """Spawn Workers for each task, run in parallel batches, wait for all."""
        await self.events.emit(EVENT_MILESTONE_STARTED, {
            "milestone_id": self.milestone.id,
            "agent_id": self.id,
            "tasks": len(plan.steps),
        }, source=self.id, task_id=plan.task_id)

        results: list[Result] = []
        # Process in batches of max_parallel
        for i in range(0, len(plan.steps), self._max_parallel):
            batch = plan.steps[i : i + self._max_parallel]

            # Spawn workers for this batch
            worker_tasks = []
            for step in batch:
                worker = Worker(
                    config=self.config,
                    events=self.events,
                    task_step=step,
                    parent_id=self.id,
                )
                self._workers.append(worker)
                worker_tasks.append(worker.run(step.description))

            # WAIT for all workers in batch to complete
            self.state = AgentState.WAITING
            batch_results = await asyncio.gather(*worker_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    results.append(Result.fail(str(result)))
                else:
                    results.append(result)

        # Merge results
        successes = sum(1 for r in results if r.success)
        all_outputs = []
        for r in results:
            prefix = "OK" if r.success else "FAIL"
            value = r.value if r.success else r.error
            all_outputs.append(f"[{prefix}] {value}")

        summary = "\n".join(all_outputs)
        success = successes == len(results)

        # Share findings with other SubAgents if we discovered something useful
        if success and all_outputs:
            await self.events.emit(EVENT_FINDING_SHARED, {
                "milestone_id": self.milestone.id,
                "summary": summary[:500],
            }, source=self.id, task_id=plan.task_id)

        event_type = EVENT_MILESTONE_COMPLETED if success else EVENT_MILESTONE_FAILED
        await self.events.emit(event_type, {
            "milestone_id": self.milestone.id,
            "success": success,
            "tasks_completed": successes,
            "tasks_total": len(results),
        }, source=self.id, task_id=plan.task_id)

        return Result.ok(summary) if success else Result.fail(summary)

    async def review(self, result: Result) -> Result:
        """Review milestone output — pass through for now."""
        # Unregister event handler to avoid leaks
        self.events.off(EVENT_FINDING_SHARED, self._handle_finding)
        return result
