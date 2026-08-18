"""Runtime provider adapter registration for Phase 20.6 execution integration."""

from __future__ import annotations

from .contracts import ProviderExecutionAdapter


class ProviderExecutionAdapterRegistryError(ValueError):
    """Raised when runtime provider adapter registration is invalid."""


class ProviderExecutionAdapterRegistry:
    """Register transient provider adapter instances by durable provider identity."""

    def __init__(self) -> None:
        self._adapters: dict[str, ProviderExecutionAdapter] = {}

    def register(self, adapter: ProviderExecutionAdapter) -> None:
        provider_id = adapter.provider_id.strip()
        if not provider_id:
            raise ProviderExecutionAdapterRegistryError("provider_id cannot be blank")
        if provider_id in self._adapters:
            raise ProviderExecutionAdapterRegistryError(
                f"Provider execution adapter already registered: {provider_id}"
            )
        self._adapters[provider_id] = adapter

    def get(self, provider_id: str) -> ProviderExecutionAdapter | None:
        return self._adapters.get(provider_id.strip())

    def require(self, provider_id: str) -> ProviderExecutionAdapter:
        normalized = provider_id.strip()
        if not normalized:
            raise ProviderExecutionAdapterRegistryError("provider_id cannot be blank")
        adapter = self._adapters.get(normalized)
        if adapter is None:
            raise ProviderExecutionAdapterRegistryError(
                f"Provider execution adapter is not registered: {normalized}"
            )
        return adapter

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
