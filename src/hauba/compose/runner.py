"""Compose Runner — Execute agent teams from ComposeConfig."""

from __future__ import annotations

from pathlib import Path

import structlog

from hauba.core.config import ConfigManager
from hauba.core.constants import (
    BUNDLED_SKILLS_DIR,
    BUNDLED_STRATEGIES_DIR,
    EVENT_COMPOSE_COMPLETED,
    EVENT_COMPOSE_FAILED,
    EVENT_COMPOSE_STARTED,
    SKILLS_DIR,
    STRATEGIES_DIR,
)
from hauba.core.dag import DAGExecutor
from hauba.core.events import EventEmitter
from hauba.core.types import ComposeConfig, Milestone, Result, TaskStep
from hauba.skills.loader import SkillLoader
from hauba.skills.strategy import StrategyEngine

logger = structlog.get_logger()


class ComposeRunner:
    """Executes a compose configuration — creates agent teams, wires DAGs, runs tasks.

    Workflow:
    1. Load skills and strategies
    2. Build milestones from agent dependencies (or strategy milestones)
    3. Wire up DAGExecutor
    4. Execute the task through the agent team
    """

    def __init__(
        self,
        config: ConfigManager,
        events: EventEmitter,
        compose: ComposeConfig,
    ) -> None:
        self._config = config
        self._events = events
        self._compose = compose
        self._output_dir = Path(compose.output).resolve()
        self._skill_loader = SkillLoader(
            skill_dirs=[SKILLS_DIR, BUNDLED_SKILLS_DIR],
        )
        self._strategy_engine = StrategyEngine(
            strategy_dirs=[STRATEGIES_DIR, BUNDLED_STRATEGIES_DIR],
        )

    async def run(self, task: str) -> Result:
        """Execute a task using the compose team.

        Args:
            task: The task description.

        Returns:
            Result with success/failure and summary.
        """
        await self._events.emit(
            EVENT_COMPOSE_STARTED,
            {"team": self._compose.team, "task": task},
        )

        try:
            # Load skills
            self._skill_loader.load_all()

            # Build milestones
            milestones = self._build_milestones(task)

            # Create and execute DAG
            dag = DAGExecutor(
                config=self._config,
                events=self._events,
            )
            dag.add_milestones(milestones)

            if not dag.validate_dag():
                return Result.fail("DAG has circular dependencies")

            result = await dag.execute()

            topic = EVENT_COMPOSE_COMPLETED if result.success else EVENT_COMPOSE_FAILED
            await self._events.emit(
                topic,
                {"team": self._compose.team, "result": result.value or result.error},
            )

            return result

        except Exception as exc:
            logger.exception("compose.run_failed", team=self._compose.team)
            await self._events.emit(
                EVENT_COMPOSE_FAILED,
                {"team": self._compose.team, "error": str(exc)},
            )
            return Result.fail(str(exc))

    def _build_milestones(self, task: str) -> list[Milestone]:
        """Build milestones from strategy or agent dependencies."""
        # Try to use strategy milestones if specified
        if self._compose.strategy:
            strategy = self._strategy_engine.get(self._compose.strategy)
            if strategy:
                milestones = strategy.to_milestone_objects()
                if milestones:
                    logger.info(
                        "compose.using_strategy",
                        strategy=strategy.name,
                        milestones=len(milestones),
                    )
                    return milestones

        # Fall back to building milestones from agent config
        return self._milestones_from_agents(task)

    def _milestones_from_agents(self, task: str) -> list[Milestone]:
        """Create milestones from compose agent definitions.

        Each agent becomes a milestone. Dependencies map directly.
        """
        milestones: list[Milestone] = []

        for name, agent_cfg in self._compose.agents.items():
            # Compose skill context for this agent
            skill_names = agent_cfg.skills
            for sname in skill_names:
                try:
                    self._skill_loader.get(sname)
                except Exception:
                    pass

            tasks = [
                TaskStep(
                    id=f"{name}-task-1",
                    description=f"[{agent_cfg.role}] {task}",
                ),
            ]

            milestone = Milestone(
                id=name,
                description=f"{agent_cfg.role}: {agent_cfg.description or task}",
                dependencies=agent_cfg.depends_on,
                tasks=tasks,
                assigned_to=name,
            )
            milestones.append(milestone)

            logger.info(
                "compose.agent_milestone",
                agent=name,
                role=agent_cfg.role,
                skills=skill_names,
                depends_on=agent_cfg.depends_on,
            )

        return milestones

    @property
    def team_name(self) -> str:
        return self._compose.team

    @property
    def agent_names(self) -> list[str]:
        return list(self._compose.agents.keys())

    def get_agent_skills(self, agent_name: str) -> list[str]:
        """Get the skill names assigned to a specific agent."""
        agent = self._compose.agents.get(agent_name)
        return agent.skills if agent else []
