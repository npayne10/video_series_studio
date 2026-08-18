"""Provider-neutral scheduling for READY ProductionTasks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import (
    ProductionCapability,
    ProductionTask,
    ProductionTaskPriority,
    ProductionTaskState,
)
from .repository import ProductionTaskRepository
from .resources import ProductionResourceCatalog


class ProductionSchedulingError(ValueError):
    """Raised when a ProductionTask schedule cannot be built safely."""


class ProductionSchedulingDeferralReason(StrEnum):
    """Provider-neutral reasons why a READY task was not scheduled."""

    NO_CAPABLE_RESOURCE = "no_capable_resource"
    NO_AVAILABLE_RESOURCE = "no_available_resource"
    RESOURCE_ALREADY_ASSIGNED = "resource_already_assigned"


@dataclass(frozen=True, slots=True)
class ProductionScheduleAssignment:
    """One provider-neutral task-to-resource assignment for a scheduling pass."""

    task_id: str
    resource_id: str
    priority: ProductionTaskPriority
    required_capabilities: tuple[ProductionCapability, ...]


@dataclass(frozen=True, slots=True)
class ProductionScheduleDeferral:
    """A READY task that could not be assigned during one scheduling pass."""

    task_id: str
    reason: ProductionSchedulingDeferralReason
    resource_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductionSchedule:
    """Deterministic provider-neutral schedule snapshot for one production."""

    production_id: str
    assignments: tuple[ProductionScheduleAssignment, ...]
    deferrals: tuple[ProductionScheduleDeferral, ...]
    ignored_task_ids: tuple[str, ...] = ()

    @property
    def scheduled_task_ids(self) -> tuple[str, ...]:
        """Return task identities assigned during this scheduling pass."""
        return tuple(assignment.task_id for assignment in self.assignments)


class ProductionScheduler:
    """Assign READY ProductionTasks to compatible available production resources.

    Scheduling is intentionally provider neutral. One ProductionResource identity may
    receive at most one task in a scheduling pass; concrete runtime capacity, leases,
    workers, providers and execution remain downstream concerns.
    """

    def build(
        self,
        production_id: str,
        tasks: tuple[ProductionTask, ...],
        resources: ProductionResourceCatalog,
    ) -> ProductionSchedule:
        """Build a deterministic schedule without mutating task or resource state."""
        normalized_production_id = production_id.strip()
        if not normalized_production_id:
            raise ProductionSchedulingError("production_id cannot be blank")
        if any(task.production_id != normalized_production_id for task in tasks):
            raise ProductionSchedulingError(
                "Production scheduler cannot mix tasks from different productions"
            )

        ready_tasks = sorted(
            (task for task in tasks if task.state is ProductionTaskState.READY),
            key=lambda task: (-int(task.priority), task.created_at, task.task_id),
        )
        ignored_task_ids = tuple(
            sorted(task.task_id for task in tasks if task.state is not ProductionTaskState.READY)
        )
        assigned_resources: set[str] = set()
        assignments: list[ProductionScheduleAssignment] = []
        deferrals: list[ProductionScheduleDeferral] = []

        for task in ready_tasks:
            evaluations = resources.evaluate(task)
            capable_resource_ids = tuple(
                match.resource_id for match in evaluations if not match.missing_capabilities
            )
            available_resource_ids = tuple(
                match.resource_id for match in evaluations if match.eligible
            )

            if not capable_resource_ids:
                deferrals.append(
                    ProductionScheduleDeferral(
                        task_id=task.task_id,
                        reason=ProductionSchedulingDeferralReason.NO_CAPABLE_RESOURCE,
                    )
                )
                continue

            if not available_resource_ids:
                deferrals.append(
                    ProductionScheduleDeferral(
                        task_id=task.task_id,
                        reason=ProductionSchedulingDeferralReason.NO_AVAILABLE_RESOURCE,
                        resource_ids=capable_resource_ids,
                    )
                )
                continue

            resource_id = next(
                (
                    candidate
                    for candidate in available_resource_ids
                    if candidate not in assigned_resources
                ),
                None,
            )
            if resource_id is None:
                deferrals.append(
                    ProductionScheduleDeferral(
                        task_id=task.task_id,
                        reason=ProductionSchedulingDeferralReason.RESOURCE_ALREADY_ASSIGNED,
                        resource_ids=available_resource_ids,
                    )
                )
                continue

            assigned_resources.add(resource_id)
            assignments.append(
                ProductionScheduleAssignment(
                    task_id=task.task_id,
                    resource_id=resource_id,
                    priority=task.priority,
                    required_capabilities=tuple(
                        sorted(task.capabilities, key=lambda capability: capability.value)
                    ),
                )
            )

        return ProductionSchedule(
            production_id=normalized_production_id,
            assignments=tuple(assignments),
            deferrals=tuple(deferrals),
            ignored_task_ids=ignored_task_ids,
        )


class ProductionSchedulingService:
    """Production-scoped scheduling service over authoritative ProductionTask state."""

    def __init__(
        self,
        repository: ProductionTaskRepository,
        resources: ProductionResourceCatalog,
        scheduler: ProductionScheduler | None = None,
    ) -> None:
        self.repository = repository
        self.resources = resources
        self.scheduler = scheduler or ProductionScheduler()

    def schedule(self, production_id: str) -> ProductionSchedule:
        """Schedule persisted READY tasks without starting or queueing execution."""
        normalized = production_id.strip()
        if not normalized:
            raise ProductionSchedulingError("production_id cannot be blank")
        tasks = self.repository.list_for_production(normalized)
        return self.scheduler.build(normalized, tasks, self.resources)
