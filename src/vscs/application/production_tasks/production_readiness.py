"""Integrated production-level readiness assessment for Phase 19.6.12."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import ProductionTaskState
from .production_queue import ProductionQueue, ProductionQueueState
from .repository import ProductionTaskRepository
from .resources import ProductionResource, ProductionResourceState
from .runtime import ProductionWorker, ProductionWorkerState
from .schedule_records import (
    ProductionScheduleRepository,
    ProductionScheduleReviewService,
    ProductionScheduleReviewState,
)


class ProductionReadinessStatus(StrEnum):
    """Integrated readiness status for one production."""

    NOT_READY = "not_ready"
    READY = "ready"
    BLOCKED = "blocked"


class ProductionReadinessSeverity(StrEnum):
    """Severity of one readiness finding."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class ProductionReadinessCode(StrEnum):
    """Stable diagnostic codes for production readiness."""

    NO_TASKS = "no_tasks"
    TASKS_NOT_READY = "tasks_not_ready"
    TASK_BLOCKED = "task_blocked"
    NO_SCHEDULE = "no_schedule"
    SCHEDULE_DEFERRED = "schedule_deferred"
    SCHEDULE_NOT_APPROVED = "schedule_not_approved"
    NO_QUEUE = "no_queue"
    QUEUE_NOT_EXECUTABLE = "queue_not_executable"
    RESOURCE_NOT_REGISTERED = "resource_not_registered"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    RESOURCE_CAPABILITY_MISMATCH = "resource_capability_mismatch"
    WORKER_NOT_REGISTERED = "worker_not_registered"
    WORKER_UNAVAILABLE = "worker_unavailable"
    WORKER_CAPABILITY_MISMATCH = "worker_capability_mismatch"
    READY_FOR_EXECUTION = "ready_for_execution"


@dataclass(frozen=True, slots=True)
class ProductionReadinessFinding:
    """One deterministic explanation contributing to production readiness."""

    code: ProductionReadinessCode
    severity: ProductionReadinessSeverity
    message: str
    task_id: str | None = None
    resource_id: str | None = None
    worker_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionReadinessAssessment:
    """Read-only integrated production readiness result."""

    production_id: str
    status: ProductionReadinessStatus
    findings: tuple[ProductionReadinessFinding, ...]
    task_count: int
    scheduled_count: int
    queue_entry_count: int
    executable_entry_count: int

    @property
    def ready(self) -> bool:
        return self.status is ProductionReadinessStatus.READY


class ProductionReadinessIntegrationService:
    """Aggregate existing production authorities into one readiness assessment.

    The service is deliberately read-only. It does not transition ProductionTasks,
    approve schedules, compile queues, register resources/workers, claim work, or
    start external execution.
    """

    _BLOCKING_TASK_STATES = frozenset(
        {
            ProductionTaskState.BLOCKED,
            ProductionTaskState.FAILED,
            ProductionTaskState.CANCELLED,
        }
    )

    def __init__(
        self,
        tasks: ProductionTaskRepository,
        schedules: ProductionScheduleRepository,
    ) -> None:
        self.tasks = tasks
        self.schedules = schedules

    def assess(
        self,
        production_id: str,
        *,
        queue: ProductionQueue | None = None,
        resources: tuple[ProductionResource, ...] = (),
        workers: tuple[ProductionWorker, ...] = (),
    ) -> ProductionReadinessAssessment:
        normalized = production_id.strip()
        if not normalized:
            raise ValueError("production_id cannot be blank")

        tasks = self.tasks.list_for_production(normalized)
        findings: list[ProductionReadinessFinding] = []
        scheduled_count = 0
        queue_entry_count = len(queue.entries) if queue is not None else 0
        executable_entry_count = 0

        if not tasks:
            findings.append(
                ProductionReadinessFinding(
                    ProductionReadinessCode.NO_TASKS,
                    ProductionReadinessSeverity.WARNING,
                    "No authoritative ProductionTasks exist for this production.",
                )
            )
            return self._assessment(
                normalized,
                findings,
                task_count=0,
                scheduled_count=0,
                queue_entry_count=queue_entry_count,
                executable_entry_count=0,
            )

        blocking_tasks = tuple(task for task in tasks if task.state in self._BLOCKING_TASK_STATES)
        for task in blocking_tasks:
            findings.append(
                ProductionReadinessFinding(
                    ProductionReadinessCode.TASK_BLOCKED,
                    ProductionReadinessSeverity.BLOCKING,
                    f"ProductionTask {task.task_id} is {task.state.value}.",
                    task_id=task.task_id,
                )
            )

        active_not_ready = tuple(
            task
            for task in tasks
            if task.state
            not in {
                ProductionTaskState.READY,
                ProductionTaskState.COMPLETED,
                ProductionTaskState.SUPERSEDED,
                *self._BLOCKING_TASK_STATES,
            }
        )
        if active_not_ready:
            findings.append(
                ProductionReadinessFinding(
                    ProductionReadinessCode.TASKS_NOT_READY,
                    ProductionReadinessSeverity.WARNING,
                    f"{len(active_not_ready)} ProductionTask(s) are not ready for scheduling/execution.",
                )
            )

        snapshot = self.schedules.latest_for_production(normalized)
        if snapshot is None:
            findings.append(
                ProductionReadinessFinding(
                    ProductionReadinessCode.NO_SCHEDULE,
                    ProductionReadinessSeverity.WARNING,
                    "No current ProductionSchedule exists.",
                )
            )
            return self._assessment(
                normalized,
                findings,
                task_count=len(tasks),
                scheduled_count=0,
                queue_entry_count=queue_entry_count,
                executable_entry_count=0,
            )

        scheduled_count = len(snapshot.schedule.assignments)
        if snapshot.schedule.deferrals:
            findings.append(
                ProductionReadinessFinding(
                    ProductionReadinessCode.SCHEDULE_DEFERRED,
                    ProductionReadinessSeverity.BLOCKING,
                    f"ProductionSchedule contains {len(snapshot.schedule.deferrals)} deferred task(s).",
                )
            )

        review = ProductionScheduleReviewService(self.schedules).view(
            snapshot.schedule_id,
            snapshot.revision,
        )
        if review.state is not ProductionScheduleReviewState.APPROVED:
            findings.append(
                ProductionReadinessFinding(
                    ProductionReadinessCode.SCHEDULE_NOT_APPROVED,
                    ProductionReadinessSeverity.WARNING,
                    f"Current ProductionSchedule review state is {review.state.value}.",
                )
            )

        if queue is None:
            findings.append(
                ProductionReadinessFinding(
                    ProductionReadinessCode.NO_QUEUE,
                    ProductionReadinessSeverity.WARNING,
                    "No in-session ProductionQueue has been compiled from the approved schedule.",
                )
            )
            return self._assessment(
                normalized,
                findings,
                task_count=len(tasks),
                scheduled_count=scheduled_count,
                queue_entry_count=0,
                executable_entry_count=0,
            )

        resource_by_id = {resource.resource_id: resource for resource in resources}
        workers_by_resource: dict[str, list[ProductionWorker]] = {}
        for worker in workers:
            workers_by_resource.setdefault(worker.resource_id, []).append(worker)

        executable_states = {
            ProductionQueueState.READY,
            ProductionQueueState.CLAIMED,
            ProductionQueueState.RUNNING,
        }
        executable_entries = tuple(
            entry for entry in queue.entries if entry.state in executable_states
        )
        executable_entry_count = len(executable_entries)
        if not executable_entries:
            findings.append(
                ProductionReadinessFinding(
                    ProductionReadinessCode.QUEUE_NOT_EXECUTABLE,
                    ProductionReadinessSeverity.BLOCKING,
                    "ProductionQueue contains no executable READY/CLAIMED/RUNNING entries.",
                )
            )

        task_by_id = {task.task_id: task for task in tasks}
        for entry in executable_entries:
            queued_task = task_by_id.get(entry.task_id)
            if queued_task is None:
                findings.append(
                    ProductionReadinessFinding(
                        ProductionReadinessCode.QUEUE_NOT_EXECUTABLE,
                        ProductionReadinessSeverity.BLOCKING,
                        f"Queue entry {entry.entry_id} references an unknown ProductionTask.",
                        task_id=entry.task_id,
                        resource_id=entry.resource_id,
                    )
                )
                continue

            resource = resource_by_id.get(entry.resource_id)
            if resource is None:
                findings.append(
                    ProductionReadinessFinding(
                        ProductionReadinessCode.RESOURCE_NOT_REGISTERED,
                        ProductionReadinessSeverity.BLOCKING,
                        f"Scheduled resource {entry.resource_id} is not registered in this session.",
                        task_id=queued_task.task_id,
                        resource_id=entry.resource_id,
                    )
                )
                continue
            if resource.state is not ProductionResourceState.AVAILABLE:
                findings.append(
                    ProductionReadinessFinding(
                        ProductionReadinessCode.RESOURCE_UNAVAILABLE,
                        ProductionReadinessSeverity.BLOCKING,
                        f"Scheduled resource {resource.resource_id} is unavailable.",
                        task_id=queued_task.task_id,
                        resource_id=resource.resource_id,
                    )
                )
            if not frozenset(queued_task.capabilities).issubset(resource.capabilities):
                findings.append(
                    ProductionReadinessFinding(
                        ProductionReadinessCode.RESOURCE_CAPABILITY_MISMATCH,
                        ProductionReadinessSeverity.BLOCKING,
                        f"Scheduled resource {resource.resource_id} no longer satisfies ProductionTask capabilities.",
                        task_id=queued_task.task_id,
                        resource_id=resource.resource_id,
                    )
                )

            candidates = tuple(workers_by_resource.get(resource.resource_id, ()))
            if not candidates:
                findings.append(
                    ProductionReadinessFinding(
                        ProductionReadinessCode.WORKER_NOT_REGISTERED,
                        ProductionReadinessSeverity.BLOCKING,
                        f"No ProductionWorker is registered for resource {resource.resource_id}.",
                        task_id=queued_task.task_id,
                        resource_id=resource.resource_id,
                    )
                )
                continue

            available = tuple(
                worker for worker in candidates if worker.state is ProductionWorkerState.AVAILABLE
            )
            if not available:
                findings.append(
                    ProductionReadinessFinding(
                        ProductionReadinessCode.WORKER_UNAVAILABLE,
                        ProductionReadinessSeverity.BLOCKING,
                        f"No available ProductionWorker is bound to resource {resource.resource_id}.",
                        task_id=queued_task.task_id,
                        resource_id=resource.resource_id,
                    )
                )
                continue

            capable = tuple(
                worker
                for worker in available
                if frozenset(queued_task.capabilities).issubset(worker.capabilities)
            )
            if not capable:
                findings.append(
                    ProductionReadinessFinding(
                        ProductionReadinessCode.WORKER_CAPABILITY_MISMATCH,
                        ProductionReadinessSeverity.BLOCKING,
                        f"Available workers for resource {resource.resource_id} lack required ProductionTask capabilities.",
                        task_id=queued_task.task_id,
                        resource_id=resource.resource_id,
                    )
                )

        if not findings:
            findings.append(
                ProductionReadinessFinding(
                    ProductionReadinessCode.READY_FOR_EXECUTION,
                    ProductionReadinessSeverity.INFO,
                    "Production is ready for provider-neutral runtime execution.",
                )
            )

        return self._assessment(
            normalized,
            findings,
            task_count=len(tasks),
            scheduled_count=scheduled_count,
            queue_entry_count=queue_entry_count,
            executable_entry_count=executable_entry_count,
        )

    @staticmethod
    def _assessment(
        production_id: str,
        findings: list[ProductionReadinessFinding],
        *,
        task_count: int,
        scheduled_count: int,
        queue_entry_count: int,
        executable_entry_count: int,
    ) -> ProductionReadinessAssessment:
        if any(finding.severity is ProductionReadinessSeverity.BLOCKING for finding in findings):
            status = ProductionReadinessStatus.BLOCKED
        elif any(finding.severity is ProductionReadinessSeverity.WARNING for finding in findings):
            status = ProductionReadinessStatus.NOT_READY
        else:
            status = ProductionReadinessStatus.READY
        return ProductionReadinessAssessment(
            production_id=production_id,
            status=status,
            findings=tuple(findings),
            task_count=task_count,
            scheduled_count=scheduled_count,
            queue_entry_count=queue_entry_count,
            executable_entry_count=executable_entry_count,
        )
