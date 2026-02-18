"""Worker — Specialist agent that executes a specific task using tools.

Phase 2: Workers can retry on failure and report artifacts for ledger verification.
"""

from __future__ import annotations

import structlog

from hauba.agents.base import BaseAgent
from hauba.brain.llm import LLMRouter
from hauba.core.config import ConfigManager
from hauba.core.constants import EVENT_TOOL_CALLED, EVENT_TOOL_RESULT, EVENT_WORKER_RESULT
from hauba.core.events import EventEmitter
from hauba.core.types import (
    LLMMessage,
    Plan,
    Result,
    TaskStep,
)
from hauba.tools.bash import BashTool
from hauba.tools.files import FileTool
from hauba.tools.git import GitTool

logger = structlog.get_logger()

MAX_RETRIES = 2

WORKER_SYSTEM_PROMPT = """You are a Worker agent in the Hauba AI engineering framework.
You receive a specific task and execute it using the available tools.

Available tools:
- bash: Run shell commands (command="...")
- files: File operations (action=read|write|append|mkdir|list, path="...", content="...")
- git: Git operations (action=status|add|commit|push|pull|diff|log|init, message="...", files="...")

Respond with EXACTLY one tool call:

TOOL: <tool_name>
ARGS:
<key>: <value>

After the result, respond with:
STATUS: <done|error> - <brief explanation>
"""


class Worker(BaseAgent):
    """Worker agent — receives a specific task, executes with tools, reports result."""

    agent_type = "worker"

    def __init__(
        self,
        config: ConfigManager,
        events: EventEmitter,
        task_step: TaskStep,
        parent_id: str = "",
    ) -> None:
        super().__init__(config, events)
        self.task_step = task_step
        self.parent_id = parent_id
        self._llm = LLMRouter(config)
        self._tools = {
            "bash": BashTool(),
            "files": FileTool(),
            "git": GitTool(),
        }

    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """Workers have minimal deliberation — they execute directly."""
        return Plan(
            task_id=task_id,
            understanding=instruction,
            approach="Direct execution",
            steps=[self.task_step],
            confidence=0.9,
        )

    async def execute(self, plan: Plan) -> Result:
        """Execute the single task using LLM-guided tool calls with retry on failure."""
        step = plan.steps[0] if plan.steps else self.task_step

        result = Result.fail("No execution attempted")
        for attempt in range(MAX_RETRIES + 1):
            result = await self._execute_once(step, plan.task_id, attempt)
            if result.success:
                return result
            if attempt < MAX_RETRIES:
                logger.info(
                    "worker.retry",
                    worker_id=self.id,
                    attempt=attempt + 1,
                    task=step.description[:50],
                )
        return result

    async def _execute_once(self, step: TaskStep, task_id: str, attempt: int) -> Result:
        """Single execution attempt for a worker task."""
        retry_hint = ""
        if attempt > 0:
            retry_hint = f"\nThis is retry attempt {attempt + 1}. The previous attempt failed. Try a different approach."

        conversation = [
            LLMMessage(role="system", content=WORKER_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=f"Execute this task: {step.description}"
                + (f"\nSuggested tool: {step.tool}" if step.tool else "")
                + retry_hint,
            ),
        ]

        response = await self._llm.complete(conversation, temperature=0.2)

        # Parse and execute tool call
        tool_name, tool_args = self._parse_tool_call(response.content)

        if tool_name and tool_name in self._tools:
            await self.events.emit(EVENT_TOOL_CALLED, {
                "tool": tool_name,
                "args": tool_args,
                "worker_id": self.id,
                "step": step.description,
            }, source=self.id, task_id=task_id)

            tool_result = await self._tools[tool_name].execute(**tool_args)

            await self.events.emit(EVENT_TOOL_RESULT, {
                "tool": tool_name,
                "success": tool_result.success,
                "output_preview": tool_result.output[:200],
            }, source=self.id, task_id=task_id)

            output = tool_result.output if tool_result.success else tool_result.error
            success = tool_result.success
        else:
            # LLM provided a direct answer without tools
            output = response.content
            success = True

        # Emit worker result
        await self.events.emit(EVENT_WORKER_RESULT, {
            "worker_id": self.id,
            "parent_id": self.parent_id,
            "task": step.description,
            "success": success,
        }, source=self.id, task_id=task_id)

        return Result.ok(output) if success else Result.fail(output)

    async def review(self, result: Result) -> Result:
        """Workers don't self-review — SubAgent reviews them."""
        return result

    def _parse_tool_call(self, text: str) -> tuple[str | None, dict]:
        """Parse TOOL/ARGS format from LLM response."""
        tool_name = None
        args: dict = {}
        in_args = False

        for line in text.strip().split("\n"):
            stripped = line.strip()
            if stripped.upper().startswith("TOOL:"):
                tool_name = stripped.split(":", 1)[1].strip().lower()
                in_args = False
            elif stripped.upper().startswith("ARGS:"):
                in_args = True
            elif in_args and ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip().lower()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    args[key] = value

        return tool_name, args
