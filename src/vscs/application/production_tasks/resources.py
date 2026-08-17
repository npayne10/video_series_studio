"""Provider-neutral production resource and capability matching for ProductionTasks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import ProductionCapability, ProductionTask


class ProductionResourceState(StrEnum):
    """Provider-neutral availability state for one production resource."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ProductionResourceCatalogError(ValueError):
    """Raised when a production resource catalog is invalid."""


@dataclass(frozen=True, slots=True)
class ProductionResource:
    """One provider-neutral resource capable of performing production work."""

    resource_id: str
    capabilities: frozenset[ProductionCapability]
    state: ProductionResourceState = ProductionResourceState.AVAILABLE
    labels: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        normalized_id = self.resource_id.strip()
        if not normalized_id:
            raise ValueError("resource_id cannot be blank")
        object.__setattr__(self, "resource_id", normalized_id)
        if not self.capabilities:
            raise ValueError("capabilities must contain at least one production capability")
        _require_unique_nonblank(self.labels, "labels")
        _require_pairs(self.metadata, "metadata")


@dataclass(frozen=True, slots=True)
class ProductionResourceMatch:
    """Deterministic capability assessment for one task/resource pair."""

    task_id: str
    resource_id: str
    eligible: bool
    available: bool
    required_capabilities: tuple[ProductionCapability, ...]
    missing_capabilities: tuple[ProductionCapability, ...]


class ProductionResourceCatalog:
    """Immutable production-resource catalog with deterministic capability matching."""

    def __init__(self, resources: tuple[ProductionResource, ...]) -> None:
        resource_ids = [resource.resource_id for resource in resources]
        if len(set(resource_ids)) != len(resource_ids):
            raise ProductionResourceCatalogError(
                "Production resource catalog contains duplicate resource identities"
            )
        self.resources = tuple(sorted(resources, key=lambda resource: resource.resource_id))
        self._resources = {resource.resource_id: resource for resource in self.resources}

    def resource(self, resource_id: str) -> ProductionResource | None:
        """Return one resource by stable identity."""
        return self._resources.get(resource_id.strip())

    def evaluate(self, task: ProductionTask) -> tuple[ProductionResourceMatch, ...]:
        """Assess every resource against one ProductionTask without selecting execution."""
        required = frozenset(task.capabilities)
        ordered_required = _ordered_capabilities(required)
        matches: list[ProductionResourceMatch] = []
        for resource in self.resources:
            missing = required.difference(resource.capabilities)
            available = resource.state is ProductionResourceState.AVAILABLE
            matches.append(
                ProductionResourceMatch(
                    task_id=task.task_id,
                    resource_id=resource.resource_id,
                    eligible=available and not missing,
                    available=available,
                    required_capabilities=ordered_required,
                    missing_capabilities=_ordered_capabilities(missing),
                )
            )
        return tuple(matches)

    def candidates_for(self, task: ProductionTask) -> tuple[ProductionResource, ...]:
        """Return all available resources satisfying every required task capability."""
        matches = {match.resource_id: match for match in self.evaluate(task)}
        return tuple(
            resource for resource in self.resources if matches[resource.resource_id].eligible
        )

    def has_candidate(self, task: ProductionTask) -> bool:
        """Return whether at least one resource can satisfy the task requirements."""
        return any(match.eligible for match in self.evaluate(task))


def _ordered_capabilities(
    capabilities: frozenset[ProductionCapability],
) -> tuple[ProductionCapability, ...]:
    return tuple(sorted(capabilities, key=lambda capability: capability.value))


def _require_unique_nonblank(values: tuple[str, ...], field_name: str) -> None:
    for value in values:
        if not value.strip():
            raise ValueError(f"{field_name} cannot contain blank values")
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} cannot contain duplicates")


def _require_pairs(values: tuple[tuple[str, str], ...], field_name: str) -> None:
    keys: set[str] = set()
    for key, value in values:
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError(f"{field_name} key cannot be blank")
        if not value.strip():
            raise ValueError(f"{field_name} value cannot be blank")
        if normalized_key in keys:
            raise ValueError(f"{field_name} cannot contain duplicate keys")
        keys.add(normalized_key)
