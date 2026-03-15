"""Hauba Engine — Custom agent loop runtime (V4).

Direct LLM API calls with full tool control, auto-compaction,
streaming, and zero SDK delegation. Inspired by OpenClaw/Pi.
"""

from hauba.engine.agent_engine import AgentEngine
from hauba.engine.types import EngineConfig, EngineResult, ProviderType

__all__ = [
    "AgentEngine",
    "EngineConfig",
    "EngineResult",
    "ProviderType",
]
