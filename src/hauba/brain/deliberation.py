"""Deliberation engine — Think before acting.

Phase 2: Integrated with Skills and Strategies for domain-aware planning.
"""

from __future__ import annotations

import asyncio
import time

import structlog

from hauba.brain.intent import Intent, parse_intent
from hauba.brain.llm import LLMRouter
from hauba.core.constants import AGENTS_DIR, DEFAULT_THINK_TIME_SECONDS
from hauba.core.types import LLMMessage, Plan, TaskStep
from hauba.skills.loader import SkillLoader
from hauba.skills.matcher import SkillMatcher
from hauba.skills.strategy import Strategy, StrategyEngine

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are the Director Agent of Hauba, an AI engineering team.
Your job is to understand the user's request, then create a detailed execution plan.

You must respond in this EXACT format:

UNDERSTANDING:
<1-3 sentences explaining what the user wants>

APPROACH:
<1-3 sentences on how you'll accomplish this>

STEPS:
1. <step description> [tool: <bash|files|git>]
2. <step description> [tool: <bash|files|git>]
...

RISKS:
- <potential risk or issue>

CONFIDENCE: <0.0 to 1.0>
"""


class DeliberationEngine:
    """Implements UNDERSTAND → PLAN phases with minimum think time.

    Phase 2: Matches tasks to skills and strategies for better planning.
    """

    def __init__(
        self,
        llm: LLMRouter,
        think_time: float = DEFAULT_THINK_TIME_SECONDS,
        skill_loader: SkillLoader | None = None,
        strategy_engine: StrategyEngine | None = None,
    ) -> None:
        self._llm = llm
        self._think_time = think_time
        self._skill_loader = skill_loader or SkillLoader()
        self._skill_matcher = SkillMatcher(self._skill_loader)
        self._strategy_engine = strategy_engine or StrategyEngine()

    async def deliberate(self, instruction: str, task_id: str) -> Plan:
        """Full deliberation: parse intent → match skills → call LLM → produce Plan."""
        start = time.monotonic()

        # Parse intent locally first
        intent = parse_intent(instruction)

        # Match skills and strategies
        skill_context = self._build_skill_context(instruction)
        strategy = self._strategy_engine.match_domain(instruction)

        # If a strategy matches, use its milestones as the plan skeleton
        if strategy and strategy.milestones:
            logger.info("deliberation.strategy_matched", strategy=strategy.name)
            plan = self._plan_from_strategy(strategy, task_id, instruction, intent)
        else:
            # Build enriched prompt with skill guidance
            system_prompt = SYSTEM_PROMPT
            if skill_context:
                system_prompt += f"\n\n## Relevant Skills\n{skill_context}"

            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=instruction),
            ]

            response = await self._llm.complete(messages, temperature=0.3)
            plan = self._parse_plan_response(response.content, task_id, intent)

        # Enforce minimum think time
        elapsed = time.monotonic() - start
        if elapsed < self._think_time:
            await asyncio.sleep(self._think_time - elapsed)

        # Save plan to disk
        await self._save_plan_files(plan, task_id)

        logger.info(
            "deliberation.complete",
            task_id=task_id,
            steps=len(plan.steps),
            confidence=plan.confidence,
        )
        return plan

    def _build_skill_context(self, instruction: str) -> str:
        """Match skills to the task and build context for the LLM."""
        matches = self._skill_matcher.match(instruction, top_k=3)
        if not matches:
            return ""

        parts = []
        for match in matches:
            parts.append(f"**{match.skill.name}** (relevance: {match.score:.0%})")
            if match.skill.approach:
                parts.append("Approach:")
                for step in match.skill.approach[:5]:
                    parts.append(f"  - {step}")
            if match.skill.constraints:
                parts.append("Constraints:")
                for c in match.skill.constraints[:3]:
                    parts.append(f"  - {c}")
            parts.append("")

        return "\n".join(parts)

    def _plan_from_strategy(
        self, strategy: Strategy, task_id: str, instruction: str, intent: Intent,
    ) -> Plan:
        """Create a Plan from a matched strategy's milestones."""
        steps: list[TaskStep] = []
        for ms in strategy.milestones:
            step_id = ms.get("id", f"{task_id}-milestone-{len(steps) + 1}")
            steps.append(TaskStep(
                id=step_id,
                description=ms.get("description", ""),
                dependencies=ms.get("dependencies", []),
            ))

        return Plan(
            task_id=task_id,
            understanding=f"{instruction} (using strategy: {strategy.name})",
            approach=f"Following {strategy.name} strategy with {len(steps)} milestones",
            steps=steps,
            risks=[],
            confidence=0.85,
        )

    def _parse_plan_response(self, text: str, task_id: str, intent: Intent) -> Plan:
        """Parse the LLM's structured response into a Plan object."""
        understanding = ""
        approach = ""
        steps: list[TaskStep] = []
        risks: list[str] = []
        confidence = 0.7

        current_section = ""
        step_count = 0

        for line in text.split("\n"):
            line_stripped = line.strip()

            if line_stripped.startswith("UNDERSTANDING:"):
                current_section = "understanding"
                rest = line_stripped[len("UNDERSTANDING:"):].strip()
                if rest:
                    understanding = rest
                continue
            elif line_stripped.startswith("APPROACH:"):
                current_section = "approach"
                rest = line_stripped[len("APPROACH:"):].strip()
                if rest:
                    approach = rest
                continue
            elif line_stripped.startswith("STEPS:"):
                current_section = "steps"
                continue
            elif line_stripped.startswith("RISKS:"):
                current_section = "risks"
                continue
            elif line_stripped.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line_stripped.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
                continue

            if not line_stripped:
                continue

            if current_section == "understanding":
                understanding += " " + line_stripped
            elif current_section == "approach":
                approach += " " + line_stripped
            elif current_section == "steps":
                # Parse "1. description [tool: bash]"
                step_count += 1
                desc = line_stripped.lstrip("0123456789.-) ")
                tool = None
                if "[tool:" in desc:
                    parts = desc.split("[tool:")
                    desc = parts[0].strip()
                    tool = parts[1].rstrip("]").strip()

                steps.append(TaskStep(
                    id=f"{task_id}-step-{step_count}",
                    description=desc,
                    tool=tool,
                ))
            elif current_section == "risks":
                risks.append(line_stripped.lstrip("- "))

        return Plan(
            task_id=task_id,
            understanding=understanding.strip(),
            approach=approach.strip(),
            steps=steps,
            risks=risks,
            confidence=max(0.0, min(1.0, confidence)),
        )

    async def _save_plan_files(self, plan: Plan, task_id: str) -> None:
        """Save understanding.md and plan.md to agent workspace."""
        workspace = AGENTS_DIR / task_id
        workspace.mkdir(parents=True, exist_ok=True)

        # understanding.md
        understanding_md = f"# Understanding\n\n{plan.understanding}\n"
        (workspace / "understanding.md").write_text(understanding_md, encoding="utf-8")

        # plan.md
        lines = [
            f"# Plan: {task_id}\n",
            f"\n## Approach\n\n{plan.approach}\n",
            f"\n## Steps ({len(plan.steps)} total)\n",
        ]
        for i, step in enumerate(plan.steps, 1):
            tool_tag = f" [{step.tool}]" if step.tool else ""
            lines.append(f"\n{i}. {step.description}{tool_tag}")

        if plan.risks:
            lines.append("\n\n## Risks\n")
            for risk in plan.risks:
                lines.append(f"\n- {risk}")

        lines.append(f"\n\n## Confidence: {plan.confidence:.1%}\n")

        (workspace / "plan.md").write_text("".join(lines), encoding="utf-8")
