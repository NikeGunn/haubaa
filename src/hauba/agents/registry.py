"""Agent Registry — tracks all active agents and their states."""

from __future__ import annotations

import time
from typing import Any

import structlog

from hauba.agents.base import BaseAgent
from hauba.core.types import AgentState

logger = structlog.get_logger()


class AgentRecord:
    """Metadata about a registered agent."""

    __slots__ = ("agent", "metadata", "parent_id", "spawned_at")

    def __init__(self, agent: BaseAgent, parent_id: str = "", metadata: dict[str, Any] | None = None) -> None:
        self.agent = agent
        self.spawned_at = time.time()
        self.parent_id = parent_id
        self.metadata = metadata or {}


class AgentRegistry:
    """Tracks all active agents and their lifecycle states.

    Provides methods for spawning, monitoring, and terminating agents.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentRecord] = {}

    def register(self, agent: BaseAgent, parent_id: str = "", metadata: dict[str, Any] | None = None) -> str:
        """Register an agent and return its ID."""
        record = AgentRecord(agent, parent_id, metadata)
        self._agents[agent.id] = record
        logger.info("registry.registered", agent_id=agent.id, agent_type=agent.agent_type, parent_id=parent_id)
        return agent.id

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info("registry.unregistered", agent_id=agent_id)

    def get(self, agent_id: str) -> BaseAgent | None:
        """Get an agent by ID."""
        record = self._agents.get(agent_id)
        return record.agent if record else None

    def get_by_type(self, agent_type: str) -> list[BaseAgent]:
        """Get all agents of a given type."""
        return [r.agent for r in self._agents.values() if r.agent.agent_type == agent_type]

    def get_by_state(self, state: AgentState) -> list[BaseAgent]:
        """Get all agents in a given state."""
        return [r.agent for r in self._agents.values() if r.agent.state == state]

    def get_children(self, parent_id: str) -> list[BaseAgent]:
        """Get all agents spawned by a parent."""
        return [r.agent for r in self._agents.values() if r.parent_id == parent_id]

    def get_active(self) -> list[BaseAgent]:
        """Get all agents that are not COMPLETED, FAILED, or TERMINATED."""
        terminal_states = {AgentState.COMPLETED, AgentState.FAILED, AgentState.TERMINATED}
        return [r.agent for r in self._agents.values() if r.agent.state not in terminal_states]

    @property
    def count(self) -> int:
        return len(self._agents)

    @property
    def active_count(self) -> int:
        return len(self.get_active())

    def summary(self) -> dict[str, Any]:
        """Return a summary of all agents grouped by state."""
        by_state: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for record in self._agents.values():
            state = record.agent.state.value
            atype = record.agent.agent_type
            by_state[state] = by_state.get(state, 0) + 1
            by_type[atype] = by_type.get(atype, 0) + 1
        return {
            "total": self.count,
            "active": self.active_count,
            "by_state": by_state,
            "by_type": by_type,
        }

    def cleanup_terminated(self) -> int:
        """Remove all terminated/completed/failed agents. Returns count removed."""
        terminal_states = {AgentState.COMPLETED, AgentState.FAILED, AgentState.TERMINATED}
        to_remove = [
            aid for aid, record in self._agents.items()
            if record.agent.state in terminal_states
        ]
        for aid in to_remove:
            del self._agents[aid]
        if to_remove:
            logger.info("registry.cleanup", removed=len(to_remove))
        return len(to_remove)
