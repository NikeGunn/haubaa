"""Tests for PluginLoader."""

from __future__ import annotations

from pathlib import Path

from hauba.plugins.loader import PluginLoader


class TestPluginLoader:
    """Test PluginLoader discovery and loading."""

    def test_discover_empty_dir(self, tmp_path: Path) -> None:
        loader = PluginLoader(plugin_dirs=[tmp_path])
        files = loader.discover()
        assert files == []

    def test_discover_finds_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "my_plugin.py").write_text("# plugin")
        (tmp_path / "__init__.py").write_text("")  # Should be skipped
        (tmp_path / "readme.txt").write_text("not a plugin")

        loader = PluginLoader(plugin_dirs=[tmp_path])
        files = loader.discover()
        assert len(files) == 1
        assert files[0].name == "my_plugin.py"

    def test_discover_nonexistent_dir(self) -> None:
        loader = PluginLoader(plugin_dirs=[Path("/nonexistent/path")])
        files = loader.discover()
        assert files == []

    def test_load_plugin_valid(self, tmp_path: Path) -> None:
        plugin_code = """
from hauba.plugins.base import BasePlugin

class TestPlugin(BasePlugin):
    name = "test"
    description = "test plugin"
    async def on_load(self): pass
    async def on_unload(self): pass

def create_plugin():
    return TestPlugin()
"""
        (tmp_path / "test_plugin.py").write_text(plugin_code)

        loader = PluginLoader(plugin_dirs=[tmp_path])
        plugin = loader.load_plugin(tmp_path / "test_plugin.py")
        assert plugin is not None
        assert plugin.name == "test"

    def test_load_plugin_missing_factory(self, tmp_path: Path) -> None:
        (tmp_path / "bad_plugin.py").write_text("x = 1")
        loader = PluginLoader(plugin_dirs=[tmp_path])
        plugin = loader.load_plugin(tmp_path / "bad_plugin.py")
        assert plugin is None

    def test_load_plugin_syntax_error(self, tmp_path: Path) -> None:
        (tmp_path / "broken.py").write_text("def broken(:\n  pass")
        loader = PluginLoader(plugin_dirs=[tmp_path])
        plugin = loader.load_plugin(tmp_path / "broken.py")
        assert plugin is None

    def test_load_all(self, tmp_path: Path) -> None:
        plugin_code = """
from hauba.plugins.base import BasePlugin

class MyPlugin(BasePlugin):
    name = "my-plugin"
    description = "works"
    async def on_load(self): pass
    async def on_unload(self): pass

def create_plugin():
    return MyPlugin()
"""
        (tmp_path / "good.py").write_text(plugin_code)
        (tmp_path / "bad.py").write_text("x = 1")

        loader = PluginLoader(plugin_dirs=[tmp_path])
        plugins = loader.load_all()
        assert len(plugins) == 1
        assert plugins[0].name == "my-plugin"
