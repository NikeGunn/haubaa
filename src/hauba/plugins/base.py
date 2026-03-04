"""Base plugin interface for Hauba."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """Abstract base class for all Hauba plugins.

    Plugins can hook into the Hauba lifecycle to extend functionality.
    Third-party services implement this interface to integrate with Hauba.

    Example:
        class MyPlugin(BasePlugin):
            name = "my-plugin"
            description = "Does something useful"

            async def on_message(self, channel, sender, text):
                if "hello" in text.lower():
                    return "Hi there from my plugin!"
                return None
    """

    name: str = ""
    description: str = ""
    version: str = "0.1.0"

    @abstractmethod
    async def on_load(self) -> None:
        """Called when the plugin is loaded. Initialize resources here."""

    @abstractmethod
    async def on_unload(self) -> None:
        """Called when the plugin is unloaded. Clean up resources here."""

    async def on_message(self, channel: str, sender: str, text: str) -> str | None:
        """Called when a message is received on any channel.

        Return a string to send as a reply, or None to pass through.
        """
        return None

    async def on_task_complete(self, task_id: str, output: str) -> None:
        """Called when a task completes execution."""
        return

    async def on_task_queued(self, task_id: str, instruction: str) -> None:
        """Called when a new task is queued."""
        return

    async def on_startup(self) -> None:
        """Called when the Hauba system starts."""
        return

    async def on_shutdown(self) -> None:
        """Called when the Hauba system shuts down."""
        return
