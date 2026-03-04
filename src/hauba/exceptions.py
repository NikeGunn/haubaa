"""Hauba custom exceptions."""

from __future__ import annotations


class HaubaError(Exception):
    """Base exception for all Hauba errors."""


class LedgerError(HaubaError):
    """TaskLedger verification failed."""


class GateCheckError(LedgerError):
    """A verification gate did not pass."""


class EngineError(HaubaError):
    """CopilotEngine execution error."""


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


class PluginError(HaubaError):
    """Plugin loading or execution error."""


class PluginNotFoundError(HaubaError):
    """Requested plugin does not exist."""


class EmailError(HaubaError):
    """Email sending failed."""


class WebFetchError(HaubaError):
    """URL fetch or content conversion failed."""
