"""Hauba Engine — Copilot SDK-powered agentic runtime.

This module wraps the GitHub Copilot SDK to provide a production-tested
agent runtime with BYOK (Bring Your Own Key) support.
"""

from hauba.engine.copilot_engine import CopilotEngine
from hauba.engine.types import EngineConfig, EngineResult, ProviderType

__all__ = [
    "CopilotEngine",
    "EngineConfig",
    "EngineResult",
    "ProviderType",
]
