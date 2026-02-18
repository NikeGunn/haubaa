"""Tests for ConfigManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from hauba.core.config import ConfigManager
from hauba.exceptions import ConfigError


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


def test_load_defaults_when_no_file(config_path: Path) -> None:
    cfg = ConfigManager(config_path)
    settings = cfg.load()
    assert settings.llm.provider == "anthropic"
    assert settings.owner_name == ""


def test_save_and_load(config_path: Path) -> None:
    cfg = ConfigManager(config_path)
    cfg.settings.owner_name = "TestUser"
    cfg.settings.llm.provider = "openai"
    cfg.save()

    cfg2 = ConfigManager(config_path)
    loaded = cfg2.load()
    assert loaded.owner_name == "TestUser"
    assert loaded.llm.provider == "openai"


def test_get_dot_notation(config_path: Path) -> None:
    cfg = ConfigManager(config_path)
    cfg.settings.llm.provider = "anthropic"
    assert cfg.get("llm.provider") == "anthropic"
    assert cfg.get("owner_name") == ""
    assert cfg.get("nonexistent") is None


def test_set_dot_notation(config_path: Path) -> None:
    cfg = ConfigManager(config_path)
    _ = cfg.settings  # initialize
    cfg.set("llm.provider", "ollama")
    assert cfg.settings.llm.provider == "ollama"


def test_set_unknown_key_raises(config_path: Path) -> None:
    cfg = ConfigManager(config_path)
    _ = cfg.settings  # initialize
    with pytest.raises(ConfigError):
        cfg.set("nonexistent.key", "value")


def test_load_invalid_json(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("not json")
    cfg = ConfigManager(config_path)
    with pytest.raises(ConfigError):
        cfg.load()
