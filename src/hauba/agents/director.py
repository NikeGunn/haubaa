"""Director Agent — the CEO agent that orchestrates AI engineering teams.

Core execution model: Recursive Agentic Loop.
The LLM IS the agent. It receives tools, decides what to do, executes,
sees results, and loops until the task is complete. No pre-planned steps
for simple tasks. Complex tasks use multi-agent delegation.

Inspired by Kilo Code's recursivelyMakeClineRequests() and
OpenClaw's runEmbeddedPiAgent() patterns.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import structlog

from hauba.agents.base import BaseAgent
from hauba.brain.deliberation import DeliberationEngine
from hauba.brain.llm import LLMRouter
from hauba.core.config import ConfigManager
from hauba.core.constants import (
    AGENTS_DIR,
    DEFAULT_MAX_AGENT_ITERATIONS,
    EVENT_LEDGER_CREATED,
    EVENT_LEDGER_GATE_FAILED,
    EVENT_LEDGER_GATE_PASSED,
    EVENT_TOOL_CALLED,
    EVENT_TOOL_RESULT,
)
from hauba.core.events import EventEmitter
from hauba.core.types import (
    Milestone,
    Plan,
    Result,
)
from hauba.exceptions import GateCheckError
from hauba.ledger.gates import VerificationGates
from hauba.ledger.tracker import TaskLedger
from hauba.ledger.wal import WAL_OP_ADD_TASK, WriteAheadLog
from hauba.memory.store import MemoryStore
from hauba.tools.base import BaseTool
from hauba.tools.bash import BashTool
from hauba.tools.files import FileTool
from hauba.tools.git import GitTool

logger = structlog.get_logger()

# Threshold: tasks with more steps than this are considered "complex"
MULTI_AGENT_THRESHOLD = 5

# Max agentic loop iterations to prevent infinite loops
MAX_ITERATIONS = DEFAULT_MAX_AGENT_ITERATIONS

DIRECTOR_SYSTEM_PROMPT = """You are a world-class autonomous software engineer. You build real, working software by using tools.

## WORKING DIRECTORY
{cwd}

## HOW YOU WORK
You receive a task and use tools to complete it. You work autonomously:
1. Think about what needs to be done
2. Use tools to create directories, write files, run commands
3. Verify your work by reading files or running tests
4. When the task is fully complete, respond with a final summary (no tool calls)

## IMPORTANT RULES
1. ALWAYS create a project directory first, then work inside it.
2. Use the `files` tool to create/write files — never use bash echo/cat for file creation.
3. For web projects: create proper HTML/CSS/JS files with modern best practices.
4. If a command fails, analyze the error and try a DIFFERENT approach.
5. Create directories before writing files in them.
6. For multi-file projects, create a logical directory structure first.
7. After creating files, verify they exist using bash `ls` or `cat`.
8. Think about what the user actually wants — produce working, complete, production-grade output.
9. Install dependencies when needed (pip, npm, etc.).
10. When you are DONE, respond with ONLY text (no tool calls) summarizing what you built.

## COMPLETION
When your task is fully complete, respond with a text summary of what you did.
Do NOT call any more tools — just describe the result.
"""


class DirectorAgent(BaseAgent):
    """The Director Agent — receives tasks, executes with a recursive agentic loop.

    For simple tasks: runs the agentic loop directly (LLM calls tools in a loop).
    For complex tasks (5+ steps): uses multi-agent delegation via DAG.
    """

    agent_type = "director"

    def __init__(
        self,
        config: ConfigManager,
        events: EventEmitter,
        workspace: Path | None = None,
    ) -> None:
        super().__init__(config, events)
        self._llm = LLMRouter(config)
        self._deliberation = DeliberationEngine(self._llm)
        self._memory = MemoryStore()
        self._tools: dict[str, BaseTool] = {
            "bash": BashTool(),
            "files": FileTool(),
            "git": GitTool(),
        }
        self._register_optional_tools()
        self._ledger: TaskLedger | None = None
        self._gates: VerificationGates | None = None
        self._wal: WriteAheadLog | None = None
        self._workspace: Path | None = workspace

    def _register_optional_tools(self) -> None:
        """Conditionally register tools if dependencies are available."""
        try:
            from hauba.tools.web import WebSearchTool

            self._tools["web_search"] = WebSearchTool()
        except Exception:
            pass

        try:
            from hauba.tools.browser import BrowserTool

            self._tools["browser"] = BrowserTool()
        except Exception:
            pass

        try:
            from hauba.tools.screen import ScreenTool

            allow = self.config.settings.allow_screen_control
            self._tools["screen"] = ScreenTool(allow_control=allow)
        except Exception:
            pass

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible tool schemas for all registered tools."""
        return [tool.tool_schema for tool in self._tools.values()]

    def _build_system_prompt(self, workspace: Path | None = None) -> str:
        """Build the system prompt with workspace directory."""
        cwd = str(workspace) if workspace else os.getcwd()
        return DIRECTOR_SYSTEM_PROMPT.format(cwd=cwd)

    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """Quick deliberation — decide if this is simple or complex.

        For simple tasks, we create a minimal plan and go straight to the agentic loop.
        For complex tasks, we create a full plan with milestones for multi-agent execution.
        """
        # Always create workspace
        self._workspace = self._workspace or (AGENTS_DIR / task_id / "workspace")
        self._workspace.mkdir(parents=True, exist_ok=True)

        # Use deliberation engine to understand the task
        plan = await self._deliberation.deliberate(instruction, task_id)

        # Initialize WAL and ledger for tracking
        agent_dir = AGENTS_DIR / task_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        self._wal = WriteAheadLog(agent_dir / "wal.log")

        if len(plan.steps) >= MULTI_AGENT_THRESHOLD:
            # Complex task — set up full TaskLedger
            plan_steps = [
                {"id": step.id, "description": step.description, "dependencies": step.dependencies}
                for step in plan.steps
            ]
            self._ledger = TaskLedger.from_plan(plan_steps, task_id, agent_dir)
            self._gates = VerificationGates(self._ledger)

            for step in plan.steps:
                self._wal.append(
                    WAL_OP_ADD_TASK,
                    step.id,
                    {"description": step.description, "dependencies": step.dependencies},
                )

            self._gates.gate_1_pre_execution()

            todo_md = self._ledger.generate_todo_md()
            (agent_dir / "todo.md").write_text(todo_md, encoding="utf-8")

            await self.events.emit(
                EVENT_LEDGER_CREATED,
                {
                    "task_id": task_id,
                    "step_count": len(plan.steps),
                    "ledger_id": self._ledger.ledger_id,
                },
                source=self.id,
                task_id=task_id,
            )

        logger.info(
            "director.deliberation_complete",
            task_id=task_id,
            steps=len(plan.steps),
            mode="multi-agent" if len(plan.steps) >= MULTI_AGENT_THRESHOLD else "agentic-loop",
        )
        return plan

    async def execute(self, plan: Plan) -> Result:
        """Execute the plan.

        Simple tasks: Run the agentic loop (LLM + tools in a recursive loop).
        Complex tasks: Use DAG executor with SubAgent teams.
        """
        await self._memory.init()

        is_complex = len(plan.steps) >= MULTI_AGENT_THRESHOLD

        if is_complex:
            result = await self._execute_multi_agent(plan)
        else:
            # Simple task: use the agentic loop directly
            result = await self._agentic_loop(plan.understanding, plan.task_id)

        # Save task history
        status = "completed" if result.success else "failed"
        await self._memory.save_task(plan.task_id, plan.understanding, status)
        await self._memory.close()

        # Close browser if used
        browser = self._tools.get("browser")
        if browser and hasattr(browser, "close"):
            try:
                await browser.close()  # type: ignore[attr-defined]
            except Exception:
                pass

        return result

    async def _agentic_loop(self, instruction: str, task_id: str) -> Result:
        """The core recursive agentic loop.

        This is the heart of Hauba's execution engine. The LLM receives tools
        and calls them in a loop until the task is complete.

        Flow:
        1. Send conversation + tools to LLM
        2. If LLM returns tool calls → execute them, append results, loop
        3. If LLM returns text only → task is done, return result
        4. Max iterations guard prevents infinite loops
        """
        workspace = self._workspace or Path.cwd()
        tool_schemas = self._get_tool_schemas()

        # Build conversation with OpenAI message format (dicts, not LLMMessage)
        conversation: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt(workspace)},
            {"role": "user", "content": instruction},
        ]

        all_outputs: list[str] = []

        for iteration in range(MAX_ITERATIONS):
            logger.info("director.loop_iteration", iteration=iteration + 1, task_id=task_id)

            response = await self._llm.complete_with_tools(
                messages=conversation,
                tools=tool_schemas,
                temperature=0.2,
            )

            if not response.has_tool_calls:
                # LLM is done — it responded with text only
                final_text = response.content or "Task completed."
                all_outputs.append(final_text)
                logger.info(
                    "director.loop_complete",
                    iterations=iteration + 1,
                    task_id=task_id,
                )
                return Result.ok("\n".join(all_outputs))

            # Append the assistant message with tool calls to conversation
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

            # Execute each tool call and append results
            for tool_call in response.tool_calls:
                tool = self._tools.get(tool_call.name)

                if tool is None:
                    # Unknown tool — tell the LLM
                    error_msg = f"Unknown tool: {tool_call.name}. Available tools: {', '.join(self._tools.keys())}"
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": error_msg,
                    })
                    continue

                # Emit tool called event
                await self.events.emit(
                    EVENT_TOOL_CALLED,
                    {
                        "tool": tool_call.name,
                        "args": tool_call.arguments,
                        "step": f"iteration {iteration + 1}",
                    },
                    source=self.id,
                    task_id=task_id,
                )

                # Inject workspace as cwd for bash commands
                args = dict(tool_call.arguments)
                if tool_call.name == "bash" and "cwd" not in args:
                    args["cwd"] = str(workspace)

                # Execute the tool
                tool_result = await tool.execute(**args)

                # Emit tool result event
                await self.events.emit(
                    EVENT_TOOL_RESULT,
                    {
                        "tool": tool_call.name,
                        "success": tool_result.success,
                        "output_preview": tool_result.output[:500] if tool_result.output else "",
                    },
                    source=self.id,
                    task_id=task_id,
                )

                # Build tool result message for conversation
                result_content = tool_result.output[:10000] if tool_result.output else ""
                if tool_result.error:
                    result_content += f"\nERROR: {tool_result.error[:2000]}"
                if not result_content:
                    result_content = "OK" if tool_result.success else "Failed with no output"

                conversation.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_content,
                })

                if tool_result.output:
                    all_outputs.append(f"[{tool_call.name}] {tool_result.output[:200]}")

        # Max iterations reached
        logger.warning("director.loop_max_iterations", task_id=task_id, max=MAX_ITERATIONS)
        return Result.fail(
            f"Task did not complete within {MAX_ITERATIONS} iterations. "
            f"Partial output:\n" + "\n".join(all_outputs[-10:])
        )

    async def _execute_multi_agent(self, plan: Plan) -> Result:
        """Execute complex plans via DAG with SubAgent teams."""
        from hauba.core.dag import DAGExecutor

        milestones = self._plan_to_milestones(plan)

        dag = DAGExecutor(
            config=self.config,
            events=self.events,
            ledger=self._ledger,
            workspace=self._workspace,
        )
        dag.add_milestones(milestones)

        if not dag.validate_dag():
            return Result.fail("DAG validation failed: cycle detected in dependencies")

        logger.info("director.multi_agent_start", milestones=len(milestones))
        result = await dag.execute()

        if self._ledger and self._workspace:
            agent_dir = self._workspace.parent
            todo_md = self._ledger.generate_todo_md()
            (agent_dir / "todo.md").write_text(todo_md, encoding="utf-8")

        return result

    def _plan_to_milestones(self, plan: Plan) -> list[Milestone]:
        """Convert plan steps into Milestone objects for DAG execution."""
        milestones: list[Milestone] = []
        for step in plan.steps:
            milestones.append(
                Milestone(
                    id=step.id,
                    description=step.description,
                    dependencies=step.dependencies,
                )
            )
        return milestones

    async def review(self, result: Result) -> Result:
        """Review execution — run Gate 4 (delivery) and Gate 5 (reconciliation)."""
        if not self._ledger or not self._gates:
            return result

        if not result.success:
            return result

        try:
            self._gates.gate_4_delivery()
            await self.events.emit(
                EVENT_LEDGER_GATE_PASSED,
                {
                    "gate": "delivery",
                    "verified": self._ledger.verified_count,
                    "total": self._ledger.task_count,
                },
                source=self.id,
            )

            self._gates.gate_5_reconciliation(self._ledger.task_count)
            await self.events.emit(
                EVENT_LEDGER_GATE_PASSED,
                {"gate": "reconciliation"},
                source=self.id,
            )

            if self._wal:
                self._wal.checkpoint()

            logger.info("director.delivery_verified", ledger=repr(self._ledger))
            return result

        except GateCheckError as exc:
            logger.error("director.gate_check_failed", error=str(exc))
            await self.events.emit(
                EVENT_LEDGER_GATE_FAILED,
                {"error": str(exc)},
                source=self.id,
            )
            return Result.fail(f"Delivery gate check failed: {exc}")
