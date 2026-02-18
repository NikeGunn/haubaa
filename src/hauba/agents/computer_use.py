"""Computer Use Agent — screenshot-analyze-act loop for desktop automation."""

from __future__ import annotations

import asyncio
import json

import structlog

from hauba.agents.base import BaseAgent
from hauba.brain.llm import LLMRouter
from hauba.core.config import ConfigManager
from hauba.core.constants import (
    DEFAULT_COMPUTER_USE_MAX_ITERATIONS,
    DEFAULT_SCREEN_DELAY,
    EVENT_SCREEN_CAPTURE,
    EVENT_SCREEN_CLICK,
    EVENT_SCREEN_TYPE,
)
from hauba.core.events import EventEmitter
from hauba.core.types import LLMMessage, Plan, Result, TaskStep
from hauba.tools.screen import ScreenTool

logger = structlog.get_logger()

COMPUTER_USE_SYSTEM_PROMPT = """You are a computer use agent. You see screenshots and decide actions.

For each screenshot, respond with a JSON object describing the next action:
{
    "action": "click" | "type" | "scroll" | "hotkey" | "done",
    "x": <int>,       // for click
    "y": <int>,       // for click
    "text": "<str>",  // for type
    "keys": "<str>",  // for hotkey (comma-separated, e.g. "ctrl,c")
    "clicks": <int>,  // for scroll
    "reasoning": "<why you chose this action>"
}

If the task is complete, respond with: {"action": "done", "reasoning": "..."}
If you see an error, describe it in reasoning and try an alternative approach.
"""


class ComputerUseAgent(BaseAgent):
    """Agent that controls the desktop via screenshot-analyze-act loop.

    Captures a screenshot, sends it to a vision LLM, parses the action JSON,
    executes the action via ScreenTool, then repeats until done or max iterations.
    """

    agent_type = "computer_use"

    def __init__(self, config: ConfigManager, events: EventEmitter) -> None:
        super().__init__(config, events)
        self._llm = LLMRouter(config)
        self._screen = ScreenTool(allow_control=True)
        self._max_iterations = DEFAULT_COMPUTER_USE_MAX_ITERATIONS
        self._delay = DEFAULT_SCREEN_DELAY

    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """Simple deliberation — the plan is a single step: execute the loop."""
        return Plan(
            task_id=task_id,
            understanding=instruction,
            approach="Screenshot-analyze-act loop until task complete",
            steps=[
                TaskStep(
                    id="loop",
                    description=f"Execute computer use loop: {instruction}",
                )
            ],
            confidence=0.7,
        )

    async def execute(self, plan: Plan) -> Result:
        """Run the screenshot-analyze-act loop."""
        instruction = plan.understanding
        conversation: list[LLMMessage] = [
            LLMMessage(role="system", content=COMPUTER_USE_SYSTEM_PROMPT),
            LLMMessage(role="user", content=f"Task: {instruction}"),
        ]

        for iteration in range(self._max_iterations):
            logger.info(
                "computer_use.iteration",
                iteration=iteration + 1,
                max=self._max_iterations,
            )

            # 1. Capture screenshot
            capture_result = await self._screen.execute(action="capture")
            if not capture_result.success:
                return Result.fail(f"Screenshot failed: {capture_result.error}")

            screenshot_path = capture_result.output.replace("Screenshot saved: ", "")
            await self.events.emit(
                EVENT_SCREEN_CAPTURE,
                {"path": screenshot_path, "iteration": iteration + 1},
                source=self.id,
                task_id=plan.task_id,
            )

            # 2. Send to LLM (as text description — vision integration is model-dependent)
            conversation.append(
                LLMMessage(
                    role="user",
                    content=f"[Screenshot captured: {screenshot_path}]\n"
                    f"Iteration {iteration + 1}/{self._max_iterations}. "
                    "What action should I take next?",
                )
            )

            response = await self._llm.complete(conversation, temperature=0.2)
            conversation.append(LLMMessage(role="assistant", content=response.content))

            # 3. Parse action JSON
            action_data = self._parse_action(response.content)
            if action_data is None:
                conversation.append(
                    LLMMessage(
                        role="user",
                        content="Could not parse action JSON. Please respond with valid JSON.",
                    )
                )
                continue

            action_type = action_data.get("action", "")

            # 4. Check if done
            if action_type == "done":
                reasoning = action_data.get("reasoning", "Task complete")
                logger.info("computer_use.done", reasoning=reasoning)
                return Result.ok(f"Completed in {iteration + 1} iterations: {reasoning}")

            # 5. Execute action
            action_result = await self._execute_action(action_data, plan.task_id)

            # 6. Feed result back
            conversation.append(
                LLMMessage(
                    role="user",
                    content=f"Action result: {action_result.output or action_result.error}",
                )
            )

            # 7. Delay between actions
            await asyncio.sleep(self._delay)

        return Result.fail(
            f"Max iterations ({self._max_iterations}) reached without completion"
        )

    async def _execute_action(self, action_data: dict, task_id: str) -> object:
        """Execute a single action from the LLM response."""
        from hauba.core.types import ToolResult

        action_type = action_data.get("action", "")

        if action_type == "click":
            x = action_data.get("x", 0)
            y = action_data.get("y", 0)
            await self.events.emit(
                EVENT_SCREEN_CLICK, {"x": x, "y": y}, source=self.id, task_id=task_id
            )
            return await self._screen.execute(action="click", x=x, y=y)

        elif action_type == "type":
            text = action_data.get("text", "")
            await self.events.emit(
                EVENT_SCREEN_TYPE,
                {"length": len(text)},
                source=self.id,
                task_id=task_id,
            )
            return await self._screen.execute(action="type", text=text)

        elif action_type == "scroll":
            clicks = action_data.get("clicks", 3)
            return await self._screen.execute(action="scroll", clicks=clicks)

        elif action_type == "hotkey":
            keys = action_data.get("keys", "")
            return await self._screen.execute(action="hotkey", keys=keys)

        else:
            return ToolResult(
                tool_name="screen",
                success=False,
                error=f"Unknown action: {action_type}",
                exit_code=1,
            )

    async def review(self, result: Result) -> Result:
        """Pass through — computer use results are self-evident."""
        return result

    def _parse_action(self, text: str) -> dict | None:
        """Parse JSON action from LLM response."""
        # Try to find JSON in the response
        text = text.strip()

        # Direct JSON
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # JSON in code block
        import re

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # JSON anywhere in text
        match = re.search(r"\{[^{}]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None
