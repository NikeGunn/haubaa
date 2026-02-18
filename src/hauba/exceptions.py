"""Hauba custom exceptions."""

from __future__ import annotations


class HaubaError(Exception):
    """Base exception for all Hauba errors."""


class LedgerError(HaubaError):
    """TaskLedger verification failed."""


class GateCheckError(LedgerError):
    """A verification gate did not pass."""


class AgentError(HaubaError):
    """Agent lifecycle error."""


class DeliberationError(AgentError):
    """Agent failed during deliberation phase."""


class SkillNotFoundError(HaubaError):
    """Requested skill does not exist."""


class ConfigError(HaubaError):
    """Configuration error."""


class SandboxError(HaubaError):
    """Sandbox execution error."""


class ToolNotAvailableError(HaubaError):
    """Optional tool dependency not installed."""


class BrowserError(HaubaError):
    """Browser automation error."""


class ScreenControlError(HaubaError):
    """Screen control / pyautogui error."""


class ReplayError(HaubaError):
    """Replay recording or playback error."""


class ComposeError(HaubaError):
    """Compose file parsing or execution error."""


class SkillInstallError(HaubaError):
    """Skill installation failed."""


class StrategyNotFoundError(HaubaError):
    """Requested strategy does not exist."""
