"""Provider execution adapter protocols for Phase 20."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .models import (
    ProviderExecutionHandle,
    ProviderExecutionOutput,
    ProviderExecutionRequest,
)


@dataclass(frozen=True, slots=True)
class ProviderExecutionValidation:
    """Adapter validation result before provider submission."""

    passed: bool
    messages: tuple[str, ...] = ()


@runtime_checkable
class ProviderExecutionAdapter(Protocol):
    """Provider-neutral lifecycle implemented by live provider adapters."""

    @property
    def provider_id(self) -> str:
        """Return stable provider identity."""
        ...

    def validate(self, request: ProviderExecutionRequest) -> ProviderExecutionValidation:
        """Validate one governed provider execution request."""
        ...

    def submit(self, request: ProviderExecutionRequest) -> ProviderExecutionHandle:
        """Submit one governed request and return a transient provider handle."""
        ...

    def monitor(self, handle: ProviderExecutionHandle) -> ProviderExecutionHandle:
        """Refresh provider state for one submitted execution."""
        ...

    def cancel(self, handle: ProviderExecutionHandle) -> ProviderExecutionHandle:
        """Request provider cancellation when supported."""
        ...

    def fetch_outputs(self, handle: ProviderExecutionHandle) -> tuple[ProviderExecutionOutput, ...]:
        """Return provider outputs without creating Generated Media authority."""
        ...
