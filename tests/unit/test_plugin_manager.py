"""Tests for plugin discovery, lifecycle, and capabilities."""

from pathlib import Path

import pytest

from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.plugins import (
    CapabilityNotFoundError,
    PluginLoadError,
    PluginManager,
    PluginState,
)
from vscs.infrastructure.services import ApplicationServices

PLUGIN_CODE = '''
from vscs.infrastructure.plugins import Plugin


class TestPlugin(Plugin):
    def __init__(self):
        self.initialized = False
        self.stopped = False

    def initialize(self, context):
        self.initialized = True
        self.context = context

    def shutdown(self):
        self.stopped = True

    def capability(self, name):
        if name == "text_to_speech":
            return "voice-provider"
        return super().capability(name)
'''


def build_manager(tmp_path: Path) -> tuple[PluginManager, ConfigurationService]:
    """Create a manager with isolated configuration and plugin storage."""
    configuration = ConfigurationService(tmp_path / "config" / "settings.yaml")
    configuration.load()
    services = ApplicationServices()
    services.register(ConfigurationService, configuration)
    manager = PluginManager(configuration, services, tmp_path / "plugins")
    services.register(PluginManager, manager)
    return manager, configuration


def write_plugin(
    root: Path,
    *,
    plugin_id: str = "test.voice",
    code: str = PLUGIN_CODE,
) -> Path:
    """Write a minimal plugin fixture to disk."""
    directory = root / plugin_id
    directory.mkdir(parents=True)
    (directory / "plugin.yaml").write_text(
        "\n".join(
            (
                f"id: {plugin_id}",
                "name: Test Voice Plugin",
                "version: 1.0.0",
                "entry_point: plugin.py:TestPlugin",
                "capabilities:",
                "  - text_to_speech",
            )
        ),
        encoding="utf-8",
    )
    (directory / "plugin.py").write_text(code, encoding="utf-8")
    return directory


def test_discover_does_not_execute_plugin_code(tmp_path: Path) -> None:
    """Discovery validates manifests without importing entry points."""
    manager, _ = build_manager(tmp_path)
    write_plugin(manager.plugin_directory, code="raise RuntimeError('must not execute')")

    records = manager.discover()

    assert len(records) == 1
    assert records[0].state is PluginState.DISCOVERED


def test_load_registers_declared_capability(tmp_path: Path) -> None:
    """A valid enabled plugin initializes and exposes capabilities."""
    manager, _ = build_manager(tmp_path)
    write_plugin(manager.plugin_directory)
    manager.discover()

    plugin = manager.load("test.voice")

    assert plugin.initialized  # type: ignore[attr-defined]
    assert manager.providers("text_to_speech") == ("test.voice",)
    assert manager.capability("text_to_speech") == "voice-provider"
    assert manager.plugins["test.voice"].state is PluginState.LOADED


def test_disable_is_persistent_and_removes_capabilities(tmp_path: Path) -> None:
    """Disabling a plugin unloads it and persists the preference."""
    manager, configuration = build_manager(tmp_path)
    write_plugin(manager.plugin_directory)
    manager.discover()
    plugin = manager.load("test.voice")

    manager.disable("test.voice")

    assert plugin.stopped  # type: ignore[attr-defined]
    assert manager.plugins["test.voice"].state is PluginState.DISABLED
    assert configuration.settings.plugins.disabled == ["test.voice"]
    with pytest.raises(CapabilityNotFoundError):
        manager.capability("text_to_speech")


def test_failed_plugin_is_isolated(tmp_path: Path) -> None:
    """Import failures are recorded without preventing other plugins from loading."""
    manager, _ = build_manager(tmp_path)
    write_plugin(manager.plugin_directory, plugin_id="broken.plugin", code="raise RuntimeError('broken')")
    write_plugin(manager.plugin_directory, plugin_id="test.voice")
    manager.discover()

    records = manager.load_enabled()

    states = {record.manifest.id: record.state for record in records}
    assert states["broken.plugin"] is PluginState.FAILED
    assert states["test.voice"] is PluginState.LOADED
    assert manager.capability("text_to_speech") == "voice-provider"


def test_loading_disabled_plugin_fails_clearly(tmp_path: Path) -> None:
    """Disabled plugins cannot be loaded until explicitly enabled."""
    manager, configuration = build_manager(tmp_path)
    configuration.settings.plugins.disabled = ["test.voice"]
    configuration.save()
    write_plugin(manager.plugin_directory)
    manager.discover()

    with pytest.raises(PluginLoadError):
        manager.load("test.voice")
