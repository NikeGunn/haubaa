"""Configuration manager for Hauba."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

from hauba.core.constants import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    SETTINGS_FILE,
)
from hauba.exceptions import ConfigError

logger = structlog.get_logger()


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = DEFAULT_LLM_PROVIDER
    model: str = DEFAULT_LLM_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    api_key: str = ""
    base_url: str = ""


class HaubaSettings(BaseModel):
    """Root settings model."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    owner_name: str = ""
    data_dir: str = ""
    log_level: str = "INFO"
    think_time: float = 2.0
    allow_screen_control: bool = False


class ConfigManager:
    """Manages Hauba configuration files."""

    def __init__(self, settings_path: Path | None = None) -> None:
        self._path = settings_path or SETTINGS_FILE
        self._settings: HaubaSettings | None = None

    @property
    def settings(self) -> HaubaSettings:
        """Get current settings, loading from disk if needed."""
        if self._settings is None:
            self._settings = self.load()
        return self._settings

    def load(self) -> HaubaSettings:
        """Load settings from disk."""
        if not self._path.exists():
            logger.info("config.not_found", path=str(self._path))
            return HaubaSettings()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._settings = HaubaSettings.model_validate(data)
            logger.info("config.loaded", path=str(self._path))
            return self._settings
        except (json.JSONDecodeError, ValueError) as exc:
            raise ConfigError(f"Invalid config file: {self._path}") from exc

    def save(self) -> None:
        """Save current settings to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = self.settings.model_dump(mode="json")
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("config.saved", path=str(self._path))

    def get(self, key: str) -> Any:
        """Get a nested config value using dot notation (e.g. 'llm.provider')."""
        parts = key.split(".")
        obj: Any = self.settings
        for part in parts:
            if isinstance(obj, BaseModel):
                try:
                    obj = getattr(obj, part)
                except AttributeError:
                    return None
            elif isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None
        return obj

    def set(self, key: str, value: str) -> None:
        """Set a nested config value using dot notation."""
        parts = key.split(".")
        if len(parts) == 1:
            if hasattr(self.settings, key):
                field_info = self.settings.model_fields.get(key)
                if field_info and field_info.annotation is float:
                    setattr(self.settings, key, float(value))
                else:
                    setattr(self.settings, key, value)
            else:
                raise ConfigError(f"Unknown config key: {key}")
        elif len(parts) == 2:
            parent = getattr(self.settings, parts[0], None)
            if parent is None or not isinstance(parent, BaseModel):
                raise ConfigError(f"Unknown config section: {parts[0]}")
            if hasattr(parent, parts[1]):
                field_info = parent.model_fields.get(parts[1])
                if field_info:
                    ann = field_info.annotation
                    if ann is int:
                        setattr(parent, parts[1], int(value))
                    elif ann is float:
                        setattr(parent, parts[1], float(value))
                    else:
                        setattr(parent, parts[1], value)
            else:
                raise ConfigError(f"Unknown config key: {key}")
        else:
            raise ConfigError(f"Config key too deep: {key}")
        self.save()
