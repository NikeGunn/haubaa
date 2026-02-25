"""Worker — Specialist agent that executes a specific task using a recursive agentic loop.

Workers have the same recursive tool-calling loop as the Director,
but scoped to a single task. They loop until their task is complete.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from hauba.agents.base import BaseAgent
from hauba.brain.llm import LLMRouter
from hauba.core.config import ConfigManager
from hauba.core.constants import (
    DEFAULT_MAX_WORKER_ITERATIONS,
    EVENT_TOOL_CALLED,
    EVENT_TOOL_RESULT,
    EVENT_WORKER_RESULT,
)
from hauba.core.events import EventEmitter
from hauba.core.types import (
    Plan,
    Result,
    TaskStep,
)
from hauba.tools.bash import BashTool
from hauba.tools.files import FileTool
from hauba.tools.git import GitTool

logger = structlog.get_logger()

WORKER_SYSTEM_PROMPT = """You are a specialist Worker agent. You execute ONE specific task completely and correctly.

## YOUR WORKSPACE
{cwd}

## TOOLS
- `bash`: Run shell commands with `cwd="{cwd}"`.
- `files`: Read/write/edit files. Relative paths resolve under {cwd}.
  - write: action="write", path="...", content="..."
  - read: action="read", path="..."
  - mkdir: action="mkdir", path="..."
- `git`: Git operations.

## YOUR JOB
1. Complete the assigned task fully and correctly.
2. Write complete, working code — no placeholders or TODOs.
3. If something fails, read the error and try a different approach.
4. Verify your output with bash (run the code, check output).
5. When done, respond with text only (no tool calls): state what you produced and where.
"""


class Worker(BaseAgent):
    """Worker agent — executes a specific task using a recursive agentic loop."""

    agent_type = "worker"

    def __init__(
        self,
        config: ConfigManager,
        events: EventEmitter,
        task_step: TaskStep,
        parent_id: str = "",
        workspace: Path | None = None,
    ) -> None:
        super().__init__(config, events)
        self.task_step = task_step
        self.parent_id = parent_id
        self._llm = LLMRouter(config)
        self._workspace = workspace or Path.cwd()
        self._tools = {
            "bash": BashTool(cwd=str(self._workspace)),
            "files": FileTool(),
            "git": GitTool(cwd=str(self._workspace)),
        }

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        return [tool.tool_schema for tool in self._tools.values()]

    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """Workers have minimal deliberation — they execute directly."""
        return Plan(
            task_id=task_id,
            understanding=instruction,
            approach="Direct execution via agentic loop",
            steps=[self.task_step],
            confidence=0.9,
        )

    async def execute(self, plan: Plan) -> Result:
        """Execute the task using a recursive agentic loop."""
        step = plan.steps[0] if plan.steps else self.task_step
        result = await self._agentic_loop(step.description, plan.task_id)

        # Emit worker result
        await self.events.emit(
            EVENT_WORKER_RESULT,
            {
                "worker_id": self.id,
                "parent_id": self.parent_id,
                "task": step.description,
                "success": result.success,
            },
            source=self.id,
            task_id=plan.task_id,
        )

        return result

    async def _agentic_loop(self, instruction: str, task_id: str) -> Result:
        """Recursive agentic loop for worker execution."""
        tool_schemas = self._get_tool_schemas()

        conversation: list[dict[str, Any]] = [
            {"role": "system", "content": WORKER_SYSTEM_PROMPT.format(cwd=str(self._workspace))},
            {"role": "user", "content": f"Execute this task: {instruction}"},
        ]

        for iteration in range(DEFAULT_MAX_WORKER_ITERATIONS):
            logger.info(
                "worker.loop_iteration",
                iteration=iteration + 1,
                worker_id=self.id,
                task_id=task_id,
            )

            response = await self._llm.complete_with_tools(
                messages=conversation,
                tools=tool_schemas,
                temperature=0.2,
            )

            if not response.has_tool_calls:
                # Worker is done
                final_text = response.content or "Task completed."
                logger.info(
                    "worker.loop_complete",
                    iterations=iteration + 1,
                    worker_id=self.id,
                )
                return Result.ok(final_text)

            # Append assistant message with tool calls
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": response.content}
            if response.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]
            conversation.append(assistant_msg)

            # Execute each tool call
            for tool_call in response.tool_calls:
                tool = self._tools.get(tool_call.name)

                if tool is None:
                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Unknown tool: {tool_call.name}",
                        }
                    )
                    continue

                await self.events.emit(
                    EVENT_TOOL_CALLED,
                    {
                        "tool": tool_call.name,
                        "args": tool_call.arguments,
                        "worker_id": self.id,
                        "step": instruction[:80],
                    },
                    source=self.id,
                    task_id=task_id,
                )

                # Inject cwd for bash commands
                args = dict(tool_call.arguments)
                if tool_call.name == "bash" and "cwd" not in args:
                    args["cwd"] = str(self._workspace)

                tool_result = await tool.execute(**args)

                await self.events.emit(
                    EVENT_TOOL_RESULT,
                    {
                        "tool": tool_call.name,
                        "success": tool_result.success,
                        "output_preview": tool_result.output[:200] if tool_result.output else "",
                    },
                    source=self.id,
                    task_id=task_id,
                )

                result_content = tool_result.output[:10000] if tool_result.output else ""
                if tool_result.error:
                    result_content += f"\nERROR: {tool_result.error[:2000]}"
                if not result_content:
                    result_content = "OK" if tool_result.success else "Failed with no output"

                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_content,
                    }
                )

        return Result.fail(
            f"Worker did not complete within {DEFAULT_MAX_WORKER_ITERATIONS} iterations"
        )

    async def review(self, result: Result) -> Result:
        """Workers don't self-review — SubAgent reviews them."""
        return result
