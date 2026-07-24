"""VSCS plugin discovery and lifecycle framework."""

from vscs.infrastructure.plugins.api import Plugin, PluginContext
from vscs.infrastructure.plugins.manager import (
    CapabilityNotFoundError,
    PluginError,
    PluginLoadError,
    PluginManager,
    PluginNotFoundError,
    PluginRecord,
    PluginState,
)
from vscs.infrastructure.plugins.manifest import PluginManifest, PluginManifestError

__all__ = [
    "CapabilityNotFoundError",
    "Plugin",
    "PluginContext",
    "PluginError",
    "PluginLoadError",
    "PluginManager",
    "PluginManifest",
    "PluginManifestError",
    "PluginNotFoundError",
    "PluginRecord",
    "PluginState",
]
