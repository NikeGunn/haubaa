"""Hauba plugin system — third-party service integration."""

from hauba.plugins.base import BasePlugin
from hauba.plugins.loader import PluginLoader
from hauba.plugins.registry import PluginRegistry

__all__ = ["BasePlugin", "PluginLoader", "PluginRegistry"]
