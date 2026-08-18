"""Compose Phase 20 provider registrations into live ComfyUI execution adapters."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.provider_execution import (
    ProviderRegistration,
    ProviderRegistrationState,
    RenderProviderExecutionAdapter,
)
from vscs.infrastructure.rendering import (
    ComfyUIAdapter,
    ComfyUIClient,
    ComfyUITransport,
    LiveComfyUIAdapter,
    UrllibComfyUITransport,
)


class ComfyUIProviderFactoryError(ValueError):
    """Raised when a provider registration cannot compose a live ComfyUI adapter."""


@dataclass(frozen=True, slots=True)
class ComfyUIProviderAdapterFactory:
    """Build a Phase 20 provider adapter from one durable ComfyUI registration."""

    timeout_seconds: float = 10.0

    def build(
        self,
        registration: ProviderRegistration,
        foundation: ComfyUIAdapter,
        *,
        transport: ComfyUITransport | None = None,
    ) -> RenderProviderExecutionAdapter:
        if registration.adapter_type.casefold() != "comfyui":
            raise ComfyUIProviderFactoryError(
                f"provider adapter_type is not comfyui: {registration.adapter_type}"
            )
        if registration.state is not ProviderRegistrationState.ENABLED:
            raise ComfyUIProviderFactoryError(
                f"ComfyUI provider is disabled: {registration.provider_id}"
            )
        endpoint = (registration.endpoint or "").strip().rstrip("/")
        if not endpoint:
            raise ComfyUIProviderFactoryError(
                f"ComfyUI provider requires an endpoint: {registration.provider_id}"
            )
        resolved_transport = transport or UrllibComfyUITransport(
            endpoint,
            timeout_seconds=self.timeout_seconds,
        )
        live = LiveComfyUIAdapter(
            foundation=foundation,
            client=ComfyUIClient(resolved_transport, endpoint),
        )
        return RenderProviderExecutionAdapter(registration.provider_id, live)
