"""Tests for BasePlugin interface."""

from __future__ import annotations

import pytest

from hauba.plugins.base import BasePlugin


class ConcretePlugin(BasePlugin):
    """A concrete plugin for testing."""

    name = "test-plugin"
    description = "A test plugin"
    version = "1.0.0"

    async def on_load(self) -> None:
        pass

    async def on_unload(self) -> None:
        pass


class TestBasePlugin:
    """Test BasePlugin ABC interface."""

    def test_concrete_plugin_has_attributes(self) -> None:
        plugin = ConcretePlugin()
        assert plugin.name == "test-plugin"
        assert plugin.description == "A test plugin"
        assert plugin.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_on_message_default_returns_none(self) -> None:
        plugin = ConcretePlugin()
        result = await plugin.on_message("whatsapp", "+1234", "hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_on_task_complete_default(self) -> None:
        plugin = ConcretePlugin()
        # Should not raise
        await plugin.on_task_complete("task-1", "output")

    @pytest.mark.asyncio
    async def test_on_task_queued_default(self) -> None:
        plugin = ConcretePlugin()
        await plugin.on_task_queued("task-1", "build something")

    @pytest.mark.asyncio
    async def test_on_startup_default(self) -> None:
        plugin = ConcretePlugin()
        await plugin.on_startup()

    @pytest.mark.asyncio
    async def test_on_shutdown_default(self) -> None:
        plugin = ConcretePlugin()
        await plugin.on_shutdown()

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            BasePlugin()  # type: ignore[abstract]
