"""Plugin discovery, loading, lifecycle, and capability management."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any

from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.plugins.api import Plugin, PluginContext
from vscs.infrastructure.plugins.manifest import PluginManifest, PluginManifestError
from vscs.infrastructure.services import ApplicationServices


class PluginError(RuntimeError):
    """Base exception for plugin framework failures."""


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin has not been discovered."""


class PluginLoadError(PluginError):
    """Raised when a plugin cannot be imported or initialized."""


class CapabilityNotFoundError(PluginError):
    """Raised when no loaded plugin provides a capability."""


class PluginState(StrEnum):
    """Current lifecycle state of a discovered plugin."""

    DISCOVERED = "discovered"
    DISABLED = "disabled"
    LOADED = "loaded"
    FAILED = "failed"


@dataclass(slots=True)
class PluginRecord:
    """Runtime state associated with one discovered manifest."""

    manifest: PluginManifest
    directory: Path
    state: PluginState = PluginState.DISCOVERED
    instance: Plugin | None = None
    error: str | None = None


class PluginManager:
    """Discover and safely manage application plugins."""

    MANIFEST_NAME = "plugin.yaml"

    def __init__(
        self,
        configuration: ConfigurationService,
        services: ApplicationServices,
        plugin_directory: Path | None = None,
    ) -> None:
        self.configuration = configuration
        self.services = services
        self.plugin_directory = plugin_directory or configuration.config_path.parent / "plugins"
        self.plugins: dict[str, PluginRecord] = {}
        self._capabilities: dict[str, list[str]] = {}
        self._logger = LoggingService.get_logger("plugins")

    def discover(self) -> tuple[PluginRecord, ...]:
        """Discover manifests without executing plugin code."""
        self.plugin_directory.mkdir(parents=True, exist_ok=True)
        self.plugins.clear()
        self._capabilities.clear()
        for manifest_path in sorted(self.plugin_directory.glob(f"*/{self.MANIFEST_NAME}")):
            try:
                manifest = PluginManifest.load(manifest_path)
                if manifest.id in self.plugins:
                    raise PluginManifestError(f"Duplicate plugin id: {manifest.id}")
                record = PluginRecord(manifest=manifest, directory=manifest_path.parent)
                if manifest.id in self.configuration.settings.plugins.disabled:
                    record.state = PluginState.DISABLED
                self.plugins[manifest.id] = record
            except PluginManifestError as exc:
                self._logger.error("Plugin discovery failed for %s: %s", manifest_path, exc)
        self._logger.info("Discovered %s plugin(s)", len(self.plugins))
        return tuple(self.plugins.values())

    def load_enabled(self) -> tuple[PluginRecord, ...]:
        """Load every discovered plugin that is not disabled."""
        for plugin_id, record in self.plugins.items():
            if record.state is PluginState.DISCOVERED:
                try:
                    self.load(plugin_id)
                except PluginLoadError:
                    continue
        return tuple(self.plugins.values())

    def load(self, plugin_id: str) -> Plugin:
        """Import and initialize one discovered plugin."""
        record = self._require_record(plugin_id)
        if record.state is PluginState.DISABLED:
            raise PluginLoadError(f"Plugin is disabled: {plugin_id}")
        if record.instance is not None:
            return record.instance
        try:
            plugin_type = self._load_plugin_type(record)
            instance = plugin_type()
            if not isinstance(instance, Plugin):
                raise TypeError("Plugin entry point must inherit from Plugin")
            instance.initialize(PluginContext(self.services, record.directory))
            record.instance = instance
            record.state = PluginState.LOADED
            record.error = None
            for capability in record.manifest.capabilities:
                instance.capability(capability)
                self._capabilities.setdefault(capability, []).append(plugin_id)
        except Exception as exc:
            record.instance = None
            record.state = PluginState.FAILED
            record.error = str(exc)
            self._remove_capabilities(plugin_id)
            self._logger.exception("Plugin failed to load: %s", plugin_id)
            raise PluginLoadError(f"Unable to load plugin {plugin_id}: {exc}") from exc
        self._logger.info("Plugin loaded: %s %s", record.manifest.name, record.manifest.version)
        return instance

    def unload(self, plugin_id: str) -> None:
        """Shut down one loaded plugin and remove its capabilities."""
        record = self._require_record(plugin_id)
        if record.instance is not None:
            try:
                record.instance.shutdown()
            finally:
                record.instance = None
                self._remove_capabilities(plugin_id)
        record.state = (
            PluginState.DISABLED
            if plugin_id in self.configuration.settings.plugins.disabled
            else PluginState.DISCOVERED
        )

    def shutdown(self) -> None:
        """Shut down all loaded plugins in reverse discovery order."""
        for plugin_id in reversed(tuple(self.plugins)):
            self.unload(plugin_id)

    def disable(self, plugin_id: str) -> None:
        """Persistently disable and unload a plugin."""
        self._require_record(plugin_id)
        disabled = self.configuration.settings.plugins.disabled
        if plugin_id not in disabled:
            disabled.append(plugin_id)
            self.configuration.save()
        self.unload(plugin_id)

    def enable(self, plugin_id: str) -> Plugin:
        """Persistently enable and load a plugin."""
        record = self._require_record(plugin_id)
        disabled = self.configuration.settings.plugins.disabled
        if plugin_id in disabled:
            disabled.remove(plugin_id)
            self.configuration.save()
        record.state = PluginState.DISCOVERED
        return self.load(plugin_id)

    def providers(self, capability: str) -> tuple[str, ...]:
        """Return loaded plugin ids providing a named capability."""
        return tuple(self._capabilities.get(capability.strip().lower(), ()))

    def capability(self, capability: str, plugin_id: str | None = None) -> Any:
        """Resolve a capability implementation from a loaded plugin."""
        normalized = capability.strip().lower()
        providers = self.providers(normalized)
        selected = plugin_id or (providers[0] if providers else None)
        if selected is None or selected not in providers:
            raise CapabilityNotFoundError(f"No loaded plugin provides capability: {normalized}")
        instance = self._require_record(selected).instance
        if instance is None:
            raise CapabilityNotFoundError(f"Plugin is not loaded: {selected}")
        return instance.capability(normalized)

    def _load_plugin_type(self, record: PluginRecord) -> type[Plugin]:
        module_path_text, class_name = record.manifest.entry_point.split(":", maxsplit=1)
        module_path = record.directory / module_path_text
        if not module_path.is_file():
            raise FileNotFoundError(f"Plugin entry point not found: {module_path}")
        module_name = f"vscs_external_plugin_{record.manifest.id.replace('.', '_').replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to create import specification for {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        return self._entry_point_type(module, class_name)

    @staticmethod
    def _entry_point_type(module: ModuleType, class_name: str) -> type[Plugin]:
        plugin_type = getattr(module, class_name, None)
        if not isinstance(plugin_type, type):
            raise TypeError(f"Plugin entry-point class not found: {class_name}")
        return plugin_type

    def _remove_capabilities(self, plugin_id: str) -> None:
        for capability in tuple(self._capabilities):
            providers = self._capabilities[capability]
            self._capabilities[capability] = [item for item in providers if item != plugin_id]
            if not self._capabilities[capability]:
                del self._capabilities[capability]

    def _require_record(self, plugin_id: str) -> PluginRecord:
        try:
            return self.plugins[plugin_id]
        except KeyError as exc:
            raise PluginNotFoundError(f"Plugin has not been discovered: {plugin_id}") from exc
