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

DIRECTOR_SYSTEM_PROMPT = """You are Hauba, an elite autonomous software engineer. You build complete, working, production-grade software that humans can deploy and use immediately.

## YOUR WORKSPACE
All files go here: {cwd}

## TOOLS YOU HAVE
- `bash`: Run shell commands. Always pass `cwd` as "{cwd}" unless you need a different directory.
- `files`: Create/read/edit files. For relative paths, they resolve under {cwd} automatically.
  - `action="write"` + `path="filename.py"` + `content="..."` → creates the file
  - `action="read"` + `path="filename.py"` → reads the file
  - `action="edit"` + `path="..."` + `old_text="..."` + `new_text="..."` → replaces text
  - `action="mkdir"` + `path="dirname"` → creates a directory
  - `action="list"` + `path="."` → lists directory contents
- `git`: Run git commands (init, add, commit).

## MANDATORY EXECUTION PROTOCOL

You MUST follow this exact sequence. Do NOT skip any step.

### Phase 1: SCAFFOLD — Create project structure
1. Create the root project directory with `files mkdir`
2. Create subdirectories for the project (src/, tests/, static/, templates/, etc.)
3. Plan the complete file list before writing any code

### Phase 2: IMPLEMENT — Write ALL source files
1. Write every file with COMPLETE, WORKING code using `files write`
2. NO placeholders, NO "# TODO", NO "pass" stubs, NO "..." ellipsis
3. Every file must be syntactically valid and import-complete
4. Write files in dependency order: models/types first, then logic, then entry points
5. Include ALL imports at the top of each file
6. For Python: create requirements.txt with pinned versions
7. For Node.js: create package.json with all dependencies
8. For web apps: create complete HTML/CSS/JS files

### Phase 3: INSTALL — Set up dependencies
1. Use `bash` to install dependencies (pip install, npm install, etc.)
2. If installation fails: READ the error, check the package name, try alternatives
3. Create virtual environments if needed

### Phase 4: VERIFY — Test that everything works (MANDATORY — DO NOT SKIP)
1. Run the application or its tests with `bash`
2. Check for syntax errors: `python -m py_compile file.py` or equivalent
3. Run the main entry point and verify output
4. If ANY test or run fails:
   a. READ the full error message carefully
   b. Use `files read` to check the failing file
   c. Use `files edit` to fix the SPECIFIC issue
   d. Re-run the test/command
   e. Repeat until it PASSES — do NOT move on with broken code

### Phase 5: FINALIZE — Polish and document
1. Create README.md with: what it does, how to install, how to run, example usage
2. Use `git` to initialize repo and make initial commit
3. Only THEN respond with a text summary (no more tool calls)

## SELF-CORRECTION RULES
- If a bash command returns a non-zero exit code or ERROR: that is a BUG. You MUST fix it.
- If `python file.py` shows an ImportError: fix the import or install the package.
- If `python file.py` shows a SyntaxError: read the file and fix the syntax.
- If `python file.py` shows a TypeError/NameError: read the file and fix the code.
- NEVER say "the code should work" — PROVE it works by running it.
- NEVER give up after one failure. Try at least 3 different approaches before declaring failure.
- If you wrote a file, ALWAYS verify it by reading it back or running it.

## QUALITY STANDARDS
1. Write COMPLETE, working code that a human can run with zero modifications.
2. Every file must be syntactically correct and fully functional.
3. Include all necessary imports, dependencies, and configuration.
4. Use proper error handling (try/except, error responses, validation).
5. For web apps: include proper routing, error pages, and static file serving.
6. For APIs: include input validation, proper HTTP status codes, and error responses.
7. For CLI apps: include --help, proper argument parsing, and user-friendly output.

## COMPLETION SIGNAL
ONLY respond with text (no tool calls) when ALL of these are true:
1. All source files are written
2. Dependencies are installed
3. You have RUN the code and it WORKS (verified via bash)
4. README.md exists with run instructions

Your text summary must include: what was built, file listing, and exact commands to run it.
{skill_context}"""


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
        self._tools: dict[str, BaseTool] = {}
        self._workspace: Path | None = workspace
        self._init_tools(workspace)
        self._register_optional_tools()
        self._ledger: TaskLedger | None = None
        self._gates: VerificationGates | None = None
        self._wal: WriteAheadLog | None = None
        self._original_instruction: str = ""

    async def run(self, instruction: str) -> Result:
        """Run with the original instruction cached for the agentic loop."""
        self._original_instruction = instruction
        return await super().run(instruction)

    def _init_tools(self, workspace: Path | None) -> None:
        """Initialize core tools with workspace context."""
        cwd = str(workspace) if workspace else None
        self._tools["bash"] = BashTool(cwd=cwd)
        self._tools["files"] = FileTool(base_dir=workspace)
        self._tools["git"] = GitTool(cwd=cwd)

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

    def _build_system_prompt(self, workspace: Path | None = None, skill_context: str = "") -> str:
        """Build the system prompt with workspace directory and skill context.

        Args:
            workspace: The workspace directory path.
            skill_context: Matched skill guidance to inject into the prompt.
        """
        cwd = str(workspace) if workspace else os.getcwd()
        # Format skill context section — insert it at the end of the prompt
        skill_section = ""
        if skill_context:
            skill_section = f"\n\n{skill_context}"
        return DIRECTOR_SYSTEM_PROMPT.format(cwd=cwd, skill_context=skill_section)

    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """Quick deliberation — decide if this is simple or complex.

        For simple tasks, we create a minimal plan and go straight to the agentic loop.
        For complex tasks, we create a full plan with milestones for multi-agent execution.
        """
        # Always create workspace
        if not self._workspace:
            self._workspace = AGENTS_DIR / task_id / "workspace"
            # Reinit tools with the now-known workspace
            self._init_tools(self._workspace)
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
        Skill context from deliberation is injected into the execution prompt.
        """
        await self._memory.init()

        is_complex = len(plan.steps) >= MULTI_AGENT_THRESHOLD

        # Get skill context from deliberation for execution injection
        skill_context = self._deliberation.build_execution_skill_context(
            self._original_instruction or plan.understanding
        )

        if is_complex:
            result = await self._execute_multi_agent(plan, skill_context)
        else:
            # Simple task: use the original instruction + plan context for the agentic loop
            original = self._original_instruction or plan.understanding
            if plan.steps:
                step_hints = "\n".join(f"- {s.description}" for s in plan.steps)
                task_description = f"{original}\n\nSuggested steps:\n{step_hints}"
            else:
                task_description = original
            result = await self._agentic_loop(
                task_description, plan.task_id, skill_context=skill_context
            )

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

    async def _agentic_loop(
        self, instruction: str, task_id: str, skill_context: str = ""
    ) -> Result:
        """The core recursive agentic loop.

        This is the heart of Hauba's execution engine. The LLM receives tools
        and calls them in a loop until the task is complete.

        Flow:
        1. Send conversation + tools to LLM (enriched with skill context)
        2. If LLM returns tool calls → execute them, append results, loop
        3. If LLM returns text only → task is done, return result
        4. Max iterations guard prevents infinite loops

        Args:
            instruction: The task to execute.
            task_id: Unique task identifier.
            skill_context: Matched skill guidance injected into system prompt.
        """
        workspace = self._workspace or Path.cwd()
        tool_schemas = self._get_tool_schemas()

        # Build conversation with OpenAI message format (dicts, not LLMMessage)
        conversation: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self._build_system_prompt(workspace, skill_context),
            },
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
                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": error_msg,
                        }
                    )
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

                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_content,
                    }
                )

                if tool_result.output:
                    all_outputs.append(f"[{tool_call.name}] {tool_result.output[:200]}")

        # Max iterations reached
        logger.warning("director.loop_max_iterations", task_id=task_id, max=MAX_ITERATIONS)
        return Result.fail(
            f"Task did not complete within {MAX_ITERATIONS} iterations. "
            f"Partial output:\n" + "\n".join(all_outputs[-10:])
        )

    async def _execute_multi_agent(self, plan: Plan, skill_context: str = "") -> Result:
        """Execute complex plans via DAG with SubAgent teams."""
        from hauba.core.dag import DAGExecutor

        milestones = self._plan_to_milestones(plan)

        dag = DAGExecutor(
            config=self.config,
            events=self.events,
            ledger=self._ledger,
            workspace=self._workspace,
            skill_context=skill_context,
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
