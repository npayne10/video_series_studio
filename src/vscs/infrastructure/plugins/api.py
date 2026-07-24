"""Public contracts implemented by VSCS plugins."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.infrastructure.services import ApplicationServices


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Services and filesystem context supplied to a plugin instance."""

    services: ApplicationServices
    plugin_directory: Path


class Plugin(ABC):
    """Base class for dynamically loaded VSCS plugins."""

    def initialize(self, context: PluginContext) -> None:
        """Initialize the plugin after its manifest has been validated."""

    def shutdown(self) -> None:
        """Release resources before the plugin is unloaded."""

    def capability(self, name: str) -> Any:
        """Return the implementation exposed for a declared capability."""
        raise KeyError(name)
