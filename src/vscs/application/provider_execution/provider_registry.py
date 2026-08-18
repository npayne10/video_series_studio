"""Durable provider registration and capability resolution for Phase 20.4."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vscs.application.production_tasks import (
    ProductionCapability,
    ProductionResource,
    ProductionResourceState,
    ProductionTask,
    ProductionTaskType,
)


class ProviderRegistrationState(StrEnum):
    """Administrative provider availability independent of network health."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class ProviderHealthState(StrEnum):
    """Last-known provider health without requiring a live probe in Phase 20.4."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    """Provider configuration owned by VSCS, never by ProductionTask authority."""

    provider_id: str
    adapter_type: str
    resource_id: str
    capabilities: frozenset[ProductionCapability]
    supported_task_types: frozenset[ProductionTaskType]
    supported_media_kinds: frozenset[str]
    endpoint: str | None = None
    secret_reference: str | None = None
    state: ProviderRegistrationState = ProviderRegistrationState.ENABLED
    health: ProviderHealthState = ProviderHealthState.UNKNOWN
    configuration: tuple[tuple[str, str], ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    _SECRET_TOKENS = frozenset(
        {"api_key", "apikey", "authorization", "bearer", "password", "secret", "token"}
    )

    def __post_init__(self) -> None:
        for field_name, value in (
            ("provider_id", self.provider_id),
            ("adapter_type", self.adapter_type),
            ("resource_id", self.resource_id),
        ):
            _require_text(value, field_name)
        _optional_text(self.endpoint, "endpoint")
        _optional_text(self.secret_reference, "secret_reference")
        if not self.capabilities:
            raise ValueError("provider capabilities must not be empty")
        if not self.supported_task_types:
            raise ValueError("supported_task_types must not be empty")
        if not self.supported_media_kinds:
            raise ValueError("supported_media_kinds must not be empty")
        for value in self.supported_media_kinds:
            _require_text(value, "supported_media_kind")
        _require_pairs(self.configuration, "configuration")
        _require_pairs(self.metadata, "metadata")
        for key, _value in self.configuration:
            normalized = key.casefold().replace("-", "_")
            if normalized in self._SECRET_TOKENS or any(
                token in normalized.split("_") for token in self._SECRET_TOKENS
            ):
                raise ValueError(
                    "provider configuration may not contain credentials; use secret_reference"
                )


@dataclass(frozen=True, slots=True)
class ProviderCapabilityResolution:
    """Deterministic resolution of one task/resource/provider combination."""

    task_id: str
    resource_id: str
    provider_id: str
    eligible: bool
    reasons: tuple[str, ...]
    missing_resource_capabilities: tuple[ProductionCapability, ...]
    missing_provider_capabilities: tuple[ProductionCapability, ...]


class ProviderCapabilityResolver:
    """Resolve actual provider eligibility without changing scheduling authority."""

    def resolve(
        self,
        task: ProductionTask,
        resource: ProductionResource,
        provider: ProviderRegistration,
    ) -> ProviderCapabilityResolution:
        reasons: list[str] = []
        required = frozenset(task.capabilities)
        missing_resource = required.difference(resource.capabilities)
        missing_provider = required.difference(provider.capabilities)

        if provider.resource_id != resource.resource_id:
            reasons.append("provider-resource-mismatch")
        if resource.state is not ProductionResourceState.AVAILABLE:
            reasons.append("resource-unavailable")
        if provider.state is not ProviderRegistrationState.ENABLED:
            reasons.append("provider-disabled")
        if provider.health is ProviderHealthState.UNHEALTHY:
            reasons.append("provider-unhealthy")
        if task.task_type not in provider.supported_task_types:
            reasons.append("task-type-unsupported")
        if missing_resource:
            reasons.append("resource-capability-mismatch")
        if missing_provider:
            reasons.append("provider-capability-mismatch")

        return ProviderCapabilityResolution(
            task_id=task.task_id,
            resource_id=resource.resource_id,
            provider_id=provider.provider_id,
            eligible=not reasons,
            reasons=tuple(reasons),
            missing_resource_capabilities=_ordered(missing_resource),
            missing_provider_capabilities=_ordered(missing_provider),
        )


def _ordered(values: frozenset[ProductionCapability]) -> tuple[ProductionCapability, ...]:
    return tuple(sorted(values, key=lambda item: item.value))


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")


def _optional_text(value: str | None, field_name: str) -> None:
    if value is not None and not value.strip():
        raise ValueError(f"{field_name} cannot be blank when supplied")


def _require_pairs(values: tuple[tuple[str, str], ...], field_name: str) -> None:
    keys: set[str] = set()
    for key, value in values:
        normalized = key.strip()
        _require_text(normalized, f"{field_name} key")
        _require_text(value, f"{field_name} value")
        if normalized in keys:
            raise ValueError(f"{field_name} cannot contain duplicate keys")
        keys.add(normalized)
