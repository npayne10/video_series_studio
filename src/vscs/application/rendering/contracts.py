"""Render adapter protocol and renderer registry contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .capabilities import WorkflowCapabilities
from .jobs import RenderJob
from .models import RendererKind, RenderRequest
from .outputs import RenderOutput


@dataclass(frozen=True, slots=True)
class RequestValidation:
    """Adapter validation outcome before compilation or submission."""

    passed: bool
    messages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CompiledRenderRequest:
    """Renderer-specific payload produced from a universal request."""

    request_id: str
    renderer: RendererKind
    workflow_id: str
    payload: dict[str, object]


@runtime_checkable
class RenderAdapter(Protocol):
    """Contract implemented by every future renderer adapter."""

    renderer: RendererKind

    def capabilities(self, workflow_id: str) -> WorkflowCapabilities:
        """Return capabilities exposed by one workflow."""
        ...

    def validate_request(self, request: RenderRequest) -> RequestValidation:
        """Validate a universal request against the adapter."""
        ...

    def compile_request(self, request: RenderRequest) -> CompiledRenderRequest:
        """Compile a universal request into renderer-specific input."""
        ...

    def submit(self, request: CompiledRenderRequest) -> RenderJob:
        """Submit a compiled request and return its tracked job."""
        ...

    def monitor(self, job: RenderJob) -> RenderJob:
        """Refresh one render job's state."""
        ...

    def cancel(self, job: RenderJob) -> RenderJob:
        """Cancel one render job when supported."""
        ...

    def fetch_outputs(self, job: RenderJob) -> tuple[RenderOutput, ...]:
        """Return outputs produced by a completed job."""
        ...


class RenderAdapterRegistry:
    """Store renderer adapters without constructing any by default."""

    def __init__(self) -> None:
        self._adapters: dict[RendererKind, RenderAdapter] = {}

    def register(self, adapter: RenderAdapter) -> RenderAdapter:
        """Register or replace one renderer adapter."""
        self._adapters[adapter.renderer] = adapter
        return adapter

    def require(self, renderer: RendererKind) -> RenderAdapter:
        """Return a renderer adapter or raise when unavailable."""
        try:
            return self._adapters[renderer]
        except KeyError as exc:
            raise KeyError(f"Render adapter not registered: {renderer.value}") from exc

    def contains(self, renderer: RendererKind) -> bool:
        """Return whether an adapter is registered."""
        return renderer in self._adapters

    def renderers(self) -> tuple[RendererKind, ...]:
        """Return registered renderer kinds in stable order."""
        return tuple(sorted(self._adapters, key=str))


@dataclass(frozen=True, slots=True)
class RenderingContracts:
    """Marker service identifying the installed rendering contract version."""

    version: str = "17.4.0.1"
