"""Compose Runner — Execute agent teams from ComposeConfig using CopilotEngine."""

from __future__ import annotations

from pathlib import Path

import structlog

from hauba.core.config import ConfigManager
from hauba.core.constants import (
    BUNDLED_SKILLS_DIR,
    EVENT_COMPOSE_AGENT_COMPLETED,
    EVENT_COMPOSE_AGENT_FAILED,
    EVENT_COMPOSE_AGENT_STARTED,
    EVENT_COMPOSE_COMPLETED,
    EVENT_COMPOSE_FAILED,
    EVENT_COMPOSE_STARTED,
    SKILLS_DIR,
)
from hauba.core.events import EventEmitter
from hauba.core.types import ComposeConfig, Result
from hauba.skills.loader import SkillLoader

logger = structlog.get_logger()


class ComposeRunner:
    """Executes a compose configuration using CopilotEngine.

    Workflow:
    1. Load skills for each agent
    2. Topologically sort agents by dependencies
    3. Execute each agent's task sequentially through CopilotEngine
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

    async def run(self, task: str) -> Result:
        """Execute a task using the compose team via CopilotEngine.

        Each agent in the compose file runs as a separate CopilotEngine.execute() call,
        sequenced by dependencies (topological sort).
        """
        await self._events.emit(
            EVENT_COMPOSE_STARTED,
            {"team": self._compose.team, "task": task},
        )

        try:
            from hauba.engine.agent_engine import AgentEngine
            from hauba.engine.types import EngineConfig, ProviderType

            # Load skills
            self._skill_loader.load_all()

            # Build engine config from hauba settings
            provider_map = {
                "anthropic": ProviderType.ANTHROPIC,
                "openai": ProviderType.OPENAI,
                "ollama": ProviderType.OLLAMA,
                "deepseek": ProviderType.OPENAI,
            }
            provider = provider_map.get(self._config.settings.llm.provider, ProviderType.ANTHROPIC)

            base_url = None
            if self._config.settings.llm.provider == "deepseek":
                base_url = "https://api.deepseek.com/v1"
            elif self._config.settings.llm.provider == "ollama":
                base_url = self._config.settings.llm.base_url or "http://localhost:11434/v1"

            # Topologically sort agents
            sorted_agents = self._topological_sort()

            # Execute each agent sequentially
            results: list[str] = []
            for agent_name in sorted_agents:
                agent_cfg = self._compose.agents[agent_name]

                await self._events.emit(
                    EVENT_COMPOSE_AGENT_STARTED,
                    {"agent": agent_name, "role": agent_cfg.role},
                )

                # Build skill context for this agent
                skill_context = self._build_agent_skill_context(agent_cfg.skills)

                # Create workspace for this agent
                agent_workspace = self._output_dir / agent_name
                agent_workspace.mkdir(parents=True, exist_ok=True)

                engine_config = EngineConfig(
                    provider=provider,
                    api_key=self._config.settings.llm.api_key,
                    model=agent_cfg.model or self._config.settings.llm.model,
                    base_url=base_url,
                    working_directory=str(agent_workspace),
                )

                engine = AgentEngine(engine_config, skill_context=skill_context)

                # Build agent-specific instruction
                instruction = (
                    f"You are the {agent_cfg.role} agent. "
                    f"{agent_cfg.description or ''}\n\n"
                    f"Task: {task}\n\n"
                    f"Previous agent results:\n{chr(10).join(results[-3:]) if results else 'None (you are first)'}"
                )

                try:
                    result = await engine.execute(instruction, timeout=600.0)
                    if result.success:
                        results.append(f"[{agent_name}/{agent_cfg.role}]: {result.output[:500]}")
                        await self._events.emit(
                            EVENT_COMPOSE_AGENT_COMPLETED,
                            {"agent": agent_name, "output_length": len(result.output)},
                        )
                    else:
                        await self._events.emit(
                            EVENT_COMPOSE_AGENT_FAILED,
                            {"agent": agent_name, "error": result.error},
                        )
                        return Result.fail(f"Agent {agent_name} failed: {result.error}")
                finally:
                    await engine.stop()

            await self._events.emit(
                EVENT_COMPOSE_COMPLETED,
                {"team": self._compose.team, "agents_completed": len(sorted_agents)},
            )

            summary = (
                f"Compose team '{self._compose.team}' completed with {len(sorted_agents)} agents."
            )
            return Result.ok(summary)

        except Exception as exc:
            logger.exception("compose.run_failed", team=self._compose.team)
            await self._events.emit(
                EVENT_COMPOSE_FAILED,
                {"team": self._compose.team, "error": str(exc)},
            )
            return Result.fail(str(exc))

    def _topological_sort(self) -> list[str]:
        """Sort agents by dependencies (topological order)."""
        visited: set[str] = set()
        order: list[str] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            agent = self._compose.agents.get(name)
            if agent:
                for dep in agent.depends_on:
                    visit(dep)
            order.append(name)

        for name in self._compose.agents:
            visit(name)

        return order

    def _build_agent_skill_context(self, skill_names: list[str]) -> str:
        """Build skill context string for injection into CopilotEngine."""
        parts: list[str] = []
        for sname in skill_names:
            try:
                skill = self._skill_loader.get(sname)
                if skill:
                    parts.append(f"### {skill.name}")
                    if skill.approach:
                        parts.append("Approach:")
                        for step in skill.approach:
                            parts.append(f"  - {step}")
                    if skill.constraints:
                        parts.append("Constraints:")
                        for c in skill.constraints:
                            parts.append(f"  - {c}")
            except Exception:
                pass
        return "\n".join(parts)

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
