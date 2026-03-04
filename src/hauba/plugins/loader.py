"""Plugin loader — discover and load plugins from directories."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import structlog

from hauba.core.constants import BUNDLED_PLUGINS_DIR, PLUGINS_DIR
from hauba.plugins.base import BasePlugin

logger = structlog.get_logger()


class PluginLoader:
    """Discover and load plugins from filesystem directories.

    Scans configured directories for Python files that contain a
    `create_plugin()` function returning a BasePlugin instance.

    Example plugin file (~/.hauba/plugins/my_plugin.py):
        from hauba.plugins.base import BasePlugin

        class MyPlugin(BasePlugin):
            name = "my-plugin"
            description = "Example plugin"
            async def on_load(self): pass
            async def on_unload(self): pass

        def create_plugin() -> BasePlugin:
            return MyPlugin()
    """

    def __init__(self, plugin_dirs: list[Path] | None = None) -> None:
        self._dirs = plugin_dirs or [PLUGINS_DIR, BUNDLED_PLUGINS_DIR]

    def discover(self) -> list[Path]:
        """Find all plugin Python files in configured directories."""
        files: list[Path] = []
        for d in self._dirs:
            if d.exists() and d.is_dir():
                for f in sorted(d.glob("*.py")):
                    if f.name.startswith("_"):
                        continue
                    files.append(f)
        return files

    def load_plugin(self, path: Path) -> BasePlugin | None:
        """Load a single plugin from a Python file.

        The file must define a `create_plugin()` function that returns
        a BasePlugin instance.

        Returns None if loading fails.
        """
        try:
            module_name = f"hauba_plugin_{path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            if spec is None or spec.loader is None:
                logger.warning("plugin.load_failed", path=str(path), reason="invalid spec")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            factory = getattr(module, "create_plugin", None)
            if factory is None:
                logger.warning(
                    "plugin.load_failed",
                    path=str(path),
                    reason="no create_plugin() function",
                )
                return None

            plugin = factory()
            if not isinstance(plugin, BasePlugin):
                logger.warning(
                    "plugin.load_failed",
                    path=str(path),
                    reason="create_plugin() did not return BasePlugin",
                )
                return None

            logger.info("plugin.loaded", name=plugin.name, path=str(path))
            return plugin

        except Exception as exc:
            logger.error("plugin.load_error", path=str(path), error=str(exc))
            return None

    def load_all(self) -> list[BasePlugin]:
        """Discover and load all available plugins."""
        plugins: list[BasePlugin] = []
        for path in self.discover():
            plugin = self.load_plugin(path)
            if plugin is not None:
                plugins.append(plugin)
        return plugins
