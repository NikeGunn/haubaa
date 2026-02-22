"""Director Agent — the CEO agent that deliberates, plans, and executes using tools.

Phase 6: Enhanced with smarter tool routing, self-correction on failures,
multi-tool chain execution, and autonomous task completion.
"""

from __future__ import annotations

import os
from pathlib import Path

import structlog

from hauba.agents.base import BaseAgent
from hauba.brain.deliberation import DeliberationEngine
from hauba.brain.llm import LLMRouter
from hauba.brain.planner import TaskPlanner
from hauba.core.config import ConfigManager
from hauba.core.constants import (
    AGENTS_DIR,
    EVENT_LEDGER_CREATED,
    EVENT_LEDGER_GATE_FAILED,
    EVENT_LEDGER_GATE_PASSED,
    EVENT_LEDGER_TASK_COMPLETED,
    EVENT_LEDGER_TASK_STARTED,
    EVENT_TOOL_CALLED,
    EVENT_TOOL_RESULT,
)
from hauba.core.events import EventEmitter
from hauba.core.types import (
    LLMMessage,
    Milestone,
    Plan,
    Result,
    TaskStatus,
    TaskStep,
)
from hauba.exceptions import GateCheckError
from hauba.ledger.gates import VerificationGates
from hauba.ledger.tracker import TaskLedger
from hauba.ledger.wal import WAL_OP_ADD_TASK, WAL_OP_COMPLETE_TASK, WAL_OP_START_TASK, WriteAheadLog
from hauba.memory.store import MemoryStore
from hauba.tools.base import BaseTool
from hauba.tools.bash import BashTool
from hauba.tools.files import FileTool
from hauba.tools.git import GitTool

logger = structlog.get_logger()

# Threshold: tasks with more steps than this are considered "complex"
MULTI_AGENT_THRESHOLD = 5

# Max tool-call retries per step when a tool fails
MAX_STEP_RETRIES = 2

EXECUTOR_SYSTEM_PROMPT = """You are a world-class autonomous software engineer. You execute plans step by step, using tools to build real working software.

## WORKING DIRECTORY
{cwd}

## AVAILABLE TOOLS

### bash — Run shell commands
TOOL: bash
ARGS:
command: <shell command>
timeout: <seconds, default 120>

### files — File operations
TOOL: files
ARGS:
action: read|write|append|mkdir|list|exists|delete
path: <file path>
content: <file content for write/append>

### git — Git operations
TOOL: git
ARGS:
action: status|add|commit|push|pull|diff|log|init
message: <commit message>
files: <file paths, comma-separated>

### web_search — Search the web (if available)
TOOL: web_search
ARGS:
query: <search query>

### browser — Browser automation with persistent sessions (if available)
TOOL: browser
ARGS:
action: navigate|click|type|extract|screenshot|wait|scroll|evaluate
url: <URL for navigate>
selector: <CSS selector>
text: <text for type>
script: <JS for evaluate>

## RESPONSE FORMAT

For each step, respond with EXACTLY one tool call:

TOOL: <tool_name>
ARGS:
<key>: <value>
<key>: <value>

After seeing the tool result, respond with:
STATUS: <done|continue|error> - <explanation>

## RULES
1. ALWAYS use the files tool to create files — never use bash echo/cat for file creation.
2. For web projects: create proper HTML/CSS/JS files, use modern best practices.
3. If a tool fails, try a DIFFERENT approach — don't repeat the same failing command.
4. Use relative paths from the working directory when possible.
5. Create directories before writing files in them.
6. For multi-file projects, create a logical directory structure first.
7. Always verify your work: after creating files, use bash to check they exist.
8. Think about what the user actually wants — produce working, complete output.
"""


class DirectorAgent(BaseAgent):
    """The Director Agent — receives tasks, deliberates, executes with tools.

    Phase 6 enhancements:
    - Smarter system prompt with all available tools
    - Self-correction: retries with different approach when tools fail
    - Working directory awareness
    - Multi-tool chain execution
    """

    agent_type = "director"

    def __init__(self, config: ConfigManager, events: EventEmitter) -> None:
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
        self._workspace: Path | None = None

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

    def _build_system_prompt(self) -> str:
        """Build the system prompt with current working directory and available tools."""
        cwd = os.getcwd()
        prompt = EXECUTOR_SYSTEM_PROMPT.format(cwd=cwd)

        # Tell the LLM which optional tools are actually available
        available = list(self._tools.keys())
        prompt += f"\n## TOOLS CURRENTLY AVAILABLE: {', '.join(available)}\n"

        return prompt

    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """Use DeliberationEngine to create a plan, then create TaskLedger from it."""
        plan = await self._deliberation.deliberate(instruction, task_id)

        # Create workspace and TaskLedger from the plan
        self._workspace = AGENTS_DIR / task_id
        self._workspace.mkdir(parents=True, exist_ok=True)

        # Initialize WAL for crash recovery
        self._wal = WriteAheadLog(self._workspace / "wal.log")

        # Create TaskLedger from plan steps
        plan_steps = [
            {"id": step.id, "description": step.description, "dependencies": step.dependencies}
            for step in plan.steps
        ]
        self._ledger = TaskLedger.from_plan(plan_steps, task_id, self._workspace)
        self._gates = VerificationGates(self._ledger)

        # Log each task addition to WAL
        for step in plan.steps:
            self._wal.append(
                WAL_OP_ADD_TASK,
                step.id,
                {
                    "description": step.description,
                    "dependencies": step.dependencies,
                },
            )

        # Gate 1: Pre-execution check
        self._gates.gate_1_pre_execution()

        # Write initial TODO.md
        todo_md = self._ledger.generate_todo_md()
        (self._workspace / "todo.md").write_text(todo_md, encoding="utf-8")

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

        logger.info("director.ledger_created", task_id=task_id, steps=len(plan.steps))
        return plan

    async def execute(self, plan: Plan) -> Result:
        """Execute plan — simple tasks run directly, complex tasks use DAG."""
        await self._memory.init()

        is_complex = len(plan.steps) >= MULTI_AGENT_THRESHOLD

        if is_complex:
            result = await self._execute_multi_agent(plan)
        else:
            result = await self._execute_single_agent(plan)

        # Save task history
        status = "completed" if result.success else "failed"
        await self._memory.save_task(plan.task_id, plan.understanding, status)
        await self._memory.close()

        # Close browser if it was used
        browser = self._tools.get("browser")
        if browser and hasattr(browser, "close"):
            try:
                await browser.close()  # type: ignore[attr-defined]
            except Exception:
                pass

        return result

    async def _execute_single_agent(self, plan: Plan) -> Result:
        """Execute plan steps sequentially with TaskLedger tracking and self-correction."""
        planner = TaskPlanner(plan)
        conversation: list[LLMMessage] = [
            LLMMessage(role="system", content=self._build_system_prompt()),
            LLMMessage(
                role="user",
                content=f"Task: {plan.understanding}\n\nPlan:\n"
                + "\n".join(f"{i + 1}. {s.description}" for i, s in enumerate(plan.steps)),
            ),
        ]

        all_outputs: list[str] = []

        for step in plan.steps:
            # Ledger: start task (enforces Gate 2: dependency check)
            if self._ledger and self._wal:
                self._wal.append(WAL_OP_START_TASK, step.id)
                self._ledger.start_task(step.id)
                await self.events.emit(
                    EVENT_LEDGER_TASK_STARTED,
                    {
                        "step_id": step.id,
                        "description": step.description,
                    },
                    source=self.id,
                    task_id=plan.task_id,
                )

            planner.mark_step(step.id, TaskStatus.IN_PROGRESS)

            # Execute step with retry-on-failure
            step_success, artifact, output_line = await self._execute_step_with_retry(
                step, plan, conversation
            )

            if step_success:
                planner.mark_step(step.id, TaskStatus.VERIFIED)
            else:
                planner.mark_step(step.id, TaskStatus.FAILED)

            all_outputs.append(output_line)

            # Ledger: complete task with artifact hash (Gate 3)
            if self._ledger and self._wal:
                if planner.get_step_status(step.id) == TaskStatus.VERIFIED:
                    artifact_hash = self._ledger.complete_task(step.id, artifact=artifact)
                    self._wal.append(
                        WAL_OP_COMPLETE_TASK,
                        step.id,
                        {
                            "artifact_hash": artifact_hash,
                        },
                    )
                    await self.events.emit(
                        EVENT_LEDGER_TASK_COMPLETED,
                        {
                            "step_id": step.id,
                            "artifact_hash": artifact_hash[:16],
                        },
                        source=self.id,
                        task_id=plan.task_id,
                    )

                # Update TODO.md on disk
                todo_md = self._ledger.generate_todo_md()
                if self._workspace:
                    (self._workspace / "todo.md").write_text(todo_md, encoding="utf-8")

        success = not planner.has_failures()
        summary = "\n".join(all_outputs)

        return Result.ok(summary) if success else Result.fail(summary)

    async def _execute_step_with_retry(
        self,
        step: TaskStep,
        plan: Plan,
        conversation: list[LLMMessage],
    ) -> tuple[bool, str, str]:
        """Execute a single step, retrying with self-correction on failure.

        Returns (success, artifact, output_line).
        """
        for attempt in range(MAX_STEP_RETRIES + 1):
            # Ask LLM what to do for this step
            if attempt == 0:
                prompt = f"Execute step: {step.description}" + (
                    f" [suggested tool: {step.tool}]" if step.tool else ""
                )
            else:
                prompt = (
                    f"The previous approach FAILED. Try a DIFFERENT approach for: {step.description}\n"
                    f"Do NOT repeat the same command. Think about what went wrong and fix it."
                )

            conversation.append(LLMMessage(role="user", content=prompt))
            response = await self._llm.complete(conversation, temperature=0.2)
            conversation.append(LLMMessage(role="assistant", content=response.content))

            # Parse tool call from response
            tool_name, tool_args = self._parse_tool_call(response.content)

            if tool_name and tool_name in self._tools:
                await self.events.emit(
                    EVENT_TOOL_CALLED,
                    {
                        "tool": tool_name,
                        "args": tool_args,
                        "step": step.description,
                    },
                    source=self.id,
                    task_id=plan.task_id,
                )

                tool_result = await self._tools[tool_name].execute(**tool_args)

                await self.events.emit(
                    EVENT_TOOL_RESULT,
                    {
                        "tool": tool_name,
                        "success": tool_result.success,
                        "output_preview": tool_result.output[:200],
                    },
                    source=self.id,
                    task_id=plan.task_id,
                )

                # Feed result back to LLM
                result_text = (
                    f"Tool result ({tool_name}):\n"
                    f"Success: {tool_result.success}\n"
                    f"Output: {tool_result.output[:2000]}"
                )
                if tool_result.error:
                    result_text += f"\nError: {tool_result.error}"

                conversation.append(LLMMessage(role="user", content=result_text))

                # Get status assessment from LLM
                status_response = await self._llm.complete(conversation, temperature=0.1)
                conversation.append(LLMMessage(role="assistant", content=status_response.content))

                if tool_result.success:
                    return (
                        True,
                        tool_result.output,
                        f"✓ {step.description}: {tool_result.output[:200]}",
                    )

                # Tool failed — retry if we have attempts left
                if attempt < MAX_STEP_RETRIES:
                    logger.warning(
                        "director.step_retry",
                        step=step.description,
                        attempt=attempt + 1,
                        error=tool_result.error[:200],
                    )
                    continue

                return False, tool_result.error, f"✗ {step.description}: {tool_result.error[:200]}"
            else:
                # No tool needed or LLM provided direct answer
                return True, response.content, f"✓ {step.description}: {response.content[:200]}"

        return False, "Max retries exceeded", f"✗ {step.description}: Max retries exceeded"

    async def _execute_multi_agent(self, plan: Plan) -> Result:
        """Execute complex plans via DAG with SubAgent teams."""
        from hauba.core.dag import DAGExecutor

        milestones = self._plan_to_milestones(plan)

        dag = DAGExecutor(
            config=self.config,
            events=self.events,
            ledger=self._ledger,
        )
        dag.add_milestones(milestones)

        if not dag.validate_dag():
            return Result.fail("DAG validation failed: cycle detected in dependencies")

        logger.info("director.multi_agent_start", milestones=len(milestones))
        result = await dag.execute()

        if self._ledger and self._workspace:
            todo_md = self._ledger.generate_todo_md()
            (self._workspace / "todo.md").write_text(todo_md, encoding="utf-8")

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
                {
                    "gate": "reconciliation",
                },
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
                {
                    "error": str(exc),
                },
                source=self.id,
            )
            return Result.fail(f"Delivery gate check failed: {exc}")

    def _parse_tool_call(self, text: str) -> tuple[str | None, dict]:
        """Parse TOOL/ARGS format from LLM response.

        Supports both the standard format and variations like:
        - TOOL: bash / ARGS: / key: value
        - ```TOOL: bash ...```
        """
        tool_name = None
        args: dict = {}

        # Strip code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines_raw = cleaned.split("\n")
            # Remove first and last lines if they are fences
            if lines_raw[0].startswith("```"):
                lines_raw = lines_raw[1:]
            if lines_raw and lines_raw[-1].strip() == "```":
                lines_raw = lines_raw[:-1]
            cleaned = "\n".join(lines_raw)

        lines = cleaned.split("\n")
        in_args = False
        content_lines: list[str] = []
        collecting_content = False
        content_key = ""

        for line in lines:
            stripped = line.strip()
            if stripped.upper().startswith("TOOL:"):
                tool_name = stripped.split(":", 1)[1].strip().lower()
                in_args = False
                collecting_content = False
            elif stripped.upper().startswith("ARGS:"):
                in_args = True
                collecting_content = False
            elif stripped.upper().startswith("STATUS:"):
                # Stop parsing at STATUS line
                break
            elif in_args and ":" in stripped and not collecting_content:
                key, _, value = stripped.partition(":")
                key = key.strip().lower()
                value = value.strip().strip('"').strip("'")
                if key == "content" and not value:
                    # Multi-line content starts on next line
                    collecting_content = True
                    content_key = key
                    content_lines = []
                elif key and value:
                    args[key] = value
            elif collecting_content:
                content_lines.append(line)

        if collecting_content and content_key:
            args[content_key] = "\n".join(content_lines)

        return tool_name, args
