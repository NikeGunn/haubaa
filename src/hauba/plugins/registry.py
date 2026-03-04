"""Plugin registry — manages loaded plugins and fires hooks."""

from __future__ import annotations

import asyncio

import structlog

from hauba.plugins.base import BasePlugin

logger = structlog.get_logger()


class PluginRegistry:
    """Central registry for loaded plugins.

    Manages plugin lifecycle and dispatches hook calls to all registered plugins.

    Usage:
        registry = PluginRegistry()
        registry.register(my_plugin)
        await registry.load_all()

        # Fire hooks
        reply = await registry.fire_on_message("whatsapp", "+1234", "hello")
        await registry.fire_on_task_complete("task-123", "Done!")
    """

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._lock = asyncio.Lock()

    @property
    def plugin_count(self) -> int:
        """Number of registered plugins."""
        return len(self._plugins)

    @property
    def plugin_names(self) -> list[str]:
        """Names of all registered plugins."""
        return list(self._plugins.keys())

    def register(self, plugin: BasePlugin) -> None:
        """Register a plugin."""
        if not plugin.name:
            logger.warning("plugin.register_failed", reason="plugin has no name")
            return
        self._plugins[plugin.name] = plugin
        logger.info("plugin.registered", name=plugin.name)

    def unregister(self, name: str) -> None:
        """Unregister a plugin by name."""
        self._plugins.pop(name, None)

    def get(self, name: str) -> BasePlugin | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    async def load_all(self) -> None:
        """Call on_load() on all registered plugins."""
        async with self._lock:
            for name, plugin in self._plugins.items():
                try:
                    await plugin.on_load()
                except Exception as exc:
                    logger.error("plugin.on_load_error", name=name, error=str(exc))

    async def unload_all(self) -> None:
        """Call on_unload() on all registered plugins."""
        async with self._lock:
            for name, plugin in self._plugins.items():
                try:
                    await plugin.on_unload()
                except Exception as exc:
                    logger.error("plugin.on_unload_error", name=name, error=str(exc))

    async def fire_on_message(self, channel: str, sender: str, text: str) -> str | None:
        """Fire on_message hook. Returns first non-None reply."""
        for name, plugin in self._plugins.items():
            try:
                reply = await plugin.on_message(channel, sender, text)
                if reply is not None:
                    return reply
            except Exception as exc:
                logger.error("plugin.on_message_error", name=name, error=str(exc))
        return None

    async def fire_on_task_complete(self, task_id: str, output: str) -> None:
        """Fire on_task_complete hook on all plugins."""
        for name, plugin in self._plugins.items():
            try:
                await plugin.on_task_complete(task_id, output)
            except Exception as exc:
                logger.error("plugin.on_task_complete_error", name=name, error=str(exc))

    async def fire_on_task_queued(self, task_id: str, instruction: str) -> None:
        """Fire on_task_queued hook on all plugins."""
        for name, plugin in self._plugins.items():
            try:
                await plugin.on_task_queued(task_id, instruction)
            except Exception as exc:
                logger.error("plugin.on_task_queued_error", name=name, error=str(exc))

    async def fire_on_startup(self) -> None:
        """Fire on_startup hook on all plugins."""
        for name, plugin in self._plugins.items():
            try:
                await plugin.on_startup()
            except Exception as exc:
                logger.error("plugin.on_startup_error", name=name, error=str(exc))

    async def fire_on_shutdown(self) -> None:
        """Fire on_shutdown hook on all plugins."""
        for name, plugin in self._plugins.items():
            try:
                await plugin.on_shutdown()
            except Exception as exc:
                logger.error("plugin.on_shutdown_error", name=name, error=str(exc))

    def list_plugins(self) -> list[dict[str, str]]:
        """List all registered plugins with metadata."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "version": p.version,
            }
            for p in self._plugins.values()
        ]
