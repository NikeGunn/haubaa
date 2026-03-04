"""Tests for PluginRegistry."""

from __future__ import annotations

import pytest

from hauba.plugins.base import BasePlugin
from hauba.plugins.registry import PluginRegistry


class StubPlugin(BasePlugin):
    """Stub plugin for testing."""

    name = "stub"
    description = "A stub"

    def __init__(self, reply: str | None = None) -> None:
        self._reply = reply
        self.loaded = False
        self.unloaded = False
        self.completed_tasks: list[str] = []
        self.queued_tasks: list[str] = []

    async def on_load(self) -> None:
        self.loaded = True

    async def on_unload(self) -> None:
        self.unloaded = True

    async def on_message(self, channel: str, sender: str, text: str) -> str | None:
        return self._reply

    async def on_task_complete(self, task_id: str, output: str) -> None:
        self.completed_tasks.append(task_id)

    async def on_task_queued(self, task_id: str, instruction: str) -> None:
        self.queued_tasks.append(task_id)


class TestPluginRegistry:
    """Test PluginRegistry."""

    def test_register_and_count(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin()
        registry.register(plugin)
        assert registry.plugin_count == 1
        assert "stub" in registry.plugin_names

    def test_unregister(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin()
        registry.register(plugin)
        registry.unregister("stub")
        assert registry.plugin_count == 0

    def test_get(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin()
        registry.register(plugin)
        assert registry.get("stub") is plugin
        assert registry.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_load_all(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin()
        registry.register(plugin)
        await registry.load_all()
        assert plugin.loaded

    @pytest.mark.asyncio
    async def test_unload_all(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin()
        registry.register(plugin)
        await registry.unload_all()
        assert plugin.unloaded

    @pytest.mark.asyncio
    async def test_fire_on_message_returns_reply(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin(reply="Hello from plugin!")
        registry.register(plugin)
        result = await registry.fire_on_message("whatsapp", "+1234", "hi")
        assert result == "Hello from plugin!"

    @pytest.mark.asyncio
    async def test_fire_on_message_no_reply(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin(reply=None)
        registry.register(plugin)
        result = await registry.fire_on_message("whatsapp", "+1234", "hi")
        assert result is None

    @pytest.mark.asyncio
    async def test_fire_on_task_complete(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin()
        registry.register(plugin)
        await registry.fire_on_task_complete("task-1", "done")
        assert "task-1" in plugin.completed_tasks

    @pytest.mark.asyncio
    async def test_fire_on_task_queued(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin()
        registry.register(plugin)
        await registry.fire_on_task_queued("task-2", "build it")
        assert "task-2" in plugin.queued_tasks

    def test_list_plugins(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin()
        registry.register(plugin)
        plugins = registry.list_plugins()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "stub"

    def test_register_no_name_skips(self) -> None:
        registry = PluginRegistry()
        plugin = StubPlugin()
        plugin.name = ""
        registry.register(plugin)
        assert registry.plugin_count == 0
