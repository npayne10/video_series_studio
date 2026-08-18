"""Persistence contracts for durable provider registrations."""

from __future__ import annotations

from typing import Protocol

from .provider_registry import ProviderRegistration


class ProviderRegistrationRepositoryError(RuntimeError):
    """Raised when provider registration persistence cannot complete safely."""


class ProviderRegistrationRepository(Protocol):
    """Persistence boundary for authoritative provider registrations."""

    def get(self, provider_id: str) -> ProviderRegistration | None:
        """Return one provider registration by stable identity."""
        ...

    def save(self, provider: ProviderRegistration) -> ProviderRegistration:
        """Create or replace one provider registration."""
        ...

    def list_all(self) -> tuple[ProviderRegistration, ...]:
        """Return all provider registrations in deterministic identity order."""
        ...

    def list_for_resource(self, resource_id: str) -> tuple[ProviderRegistration, ...]:
        """Return providers bound to one ProductionResource."""
        ...
