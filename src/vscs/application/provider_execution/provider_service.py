"""Application service for provider registration and capability resolution."""

from __future__ import annotations

from dataclasses import replace

from vscs.application.production_tasks import ProductionResource, ProductionTask

from .provider_registry import (
    ProviderCapabilityResolution,
    ProviderCapabilityResolver,
    ProviderHealthState,
    ProviderRegistration,
    ProviderRegistrationState,
)
from .provider_repository import (
    ProviderRegistrationRepository,
    ProviderRegistrationRepositoryError,
)


class ProviderRegistryService:
    """Own durable provider registration and deterministic execution eligibility."""

    def __init__(
        self,
        repository: ProviderRegistrationRepository,
        resolver: ProviderCapabilityResolver | None = None,
    ) -> None:
        self.repository = repository
        self.resolver = resolver or ProviderCapabilityResolver()

    def register(self, provider: ProviderRegistration) -> ProviderRegistration:
        if self.repository.get(provider.provider_id) is not None:
            raise ProviderRegistrationRepositoryError(
                f"ProviderRegistration already exists: {provider.provider_id}"
            )
        return self.repository.save(provider)

    def save(self, provider: ProviderRegistration) -> ProviderRegistration:
        return self.repository.save(provider)

    def get(self, provider_id: str) -> ProviderRegistration | None:
        return self.repository.get(provider_id)

    def list_all(self) -> tuple[ProviderRegistration, ...]:
        return self.repository.list_all()

    def list_for_resource(self, resource_id: str) -> tuple[ProviderRegistration, ...]:
        return self.repository.list_for_resource(resource_id)

    def set_state(
        self,
        provider_id: str,
        state: ProviderRegistrationState,
    ) -> ProviderRegistration:
        provider = self._require(provider_id)
        return self.repository.save(replace(provider, state=state))

    def set_health(
        self,
        provider_id: str,
        health: ProviderHealthState,
    ) -> ProviderRegistration:
        provider = self._require(provider_id)
        return self.repository.save(replace(provider, health=health))

    def resolve(
        self,
        task: ProductionTask,
        resource: ProductionResource,
    ) -> tuple[ProviderCapabilityResolution, ...]:
        """Assess every provider bound to a scheduled resource without selecting one silently."""
        return tuple(
            self.resolver.resolve(task, resource, provider)
            for provider in self.repository.list_for_resource(resource.resource_id)
        )

    def eligible_providers(
        self,
        task: ProductionTask,
        resource: ProductionResource,
    ) -> tuple[ProviderRegistration, ...]:
        resolutions = {item.provider_id: item for item in self.resolve(task, resource)}
        return tuple(
            provider
            for provider in self.repository.list_for_resource(resource.resource_id)
            if resolutions[provider.provider_id].eligible
        )

    def _require(self, provider_id: str) -> ProviderRegistration:
        normalized = provider_id.strip()
        if not normalized:
            raise ProviderRegistrationRepositoryError("provider_id cannot be blank")
        provider = self.repository.get(normalized)
        if provider is None:
            raise ProviderRegistrationRepositoryError(
                f"ProviderRegistration not found: {normalized}"
            )
        return provider
