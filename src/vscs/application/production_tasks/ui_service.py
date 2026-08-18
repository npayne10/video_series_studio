"""Application facade used by the Production Scheduling workspace."""

from __future__ import annotations

from collections.abc import Callable

from .graph import ProductionTaskGraphIntegrationService, ProductionTaskGraphRefreshResult
from .lifecycle import ProductionTaskLifecycleService
from .models import ProductionTask
from .production_queue import ProductionQueue, ProductionQueueCompilerService
from .production_readiness import (
    ProductionReadinessAssessment,
    ProductionReadinessIntegrationService,
)
from .repository import ProductionTaskRepository
from .resources import ProductionResource, ProductionResourceCatalog
from .runtime import ProductionQueueRuntimeService, ProductionWorker, ProductionWorkerRegistry
from .schedule_records import (
    ProductionSchedulePersistenceService,
    ProductionScheduleRepository,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewRecord,
    ProductionScheduleReviewService,
    ProductionScheduleReviewView,
    ProductionScheduleSnapshot,
)
from .scheduler import ProductionSchedulingService
from .scheduling_monitoring import (
    ProductionSchedulingMonitor,
    ProductionSchedulingMonitoringSnapshot,
    ProductionSchedulingRecoveryResult,
    ProductionSchedulingRecoveryService,
)


class ProductionSchedulingUiError(RuntimeError):
    """Raised when the scheduling workspace cannot perform an application command."""


TaskRepositoryFactory = Callable[[], ProductionTaskRepository]
ScheduleRepositoryFactory = Callable[[], ProductionScheduleRepository]


class ProductionSchedulingUiService:
    """Thin application facade for operator-facing scheduling commands and queries.

    Repository factories are supplied by composition so this application layer remains
    independent of concrete persistence. Resources, workers, queues and leases stay
    session scoped until later Phase 19.6 runtime persistence/discovery work.
    """

    def __init__(
        self,
        task_repository_factory: TaskRepositoryFactory,
        schedule_repository_factory: ScheduleRepositoryFactory,
    ) -> None:
        self._task_repository_factory = task_repository_factory
        self._schedule_repository_factory = schedule_repository_factory
        self._resources: dict[str, ProductionResource] = {}
        self._workers: dict[str, ProductionWorker] = {}
        self._worker_registry = ProductionWorkerRegistry()
        self._queues: dict[str, ProductionQueue] = {}
        self._runtime_by_production: dict[str, ProductionQueueRuntimeService] = {}
        self._monitor = ProductionSchedulingMonitor()

    def register_compiled_tasks(
        self, tasks: tuple[ProductionTask, ...]
    ) -> tuple[ProductionTask, ...]:
        """Persist compiler output without changing task lifecycle state."""
        repository = self._task_repository()
        lifecycle = ProductionTaskLifecycleService(repository)
        for task in tasks:
            existing = repository.get(task.task_id)
            if existing is None:
                lifecycle.register(task)
                continue
            if not _same_compiled_contract(existing, task):
                raise ProductionSchedulingUiError(
                    f"ProductionTask already exists with different governed content: {task.task_id}"
                )
        return tasks

    def tasks(self, production_id: str) -> tuple[ProductionTask, ...]:
        return self._task_repository().list_for_production(
            self._require_production_id(production_id)
        )

    def register_resource(self, resource: ProductionResource) -> ProductionResource:
        self._resources[resource.resource_id] = resource
        return resource

    def resources(self) -> tuple[ProductionResource, ...]:
        return tuple(self._resources[key] for key in sorted(self._resources))

    def register_worker(self, worker: ProductionWorker) -> ProductionWorker:
        """Register or update one session worker under a stable worker identity."""
        self._workers[worker.worker_id] = worker
        refreshed_registry = ProductionWorkerRegistry()
        for worker_id in sorted(self._workers):
            refreshed_registry.register(self._workers[worker_id])
        self._worker_registry = refreshed_registry
        for runtime in self._runtime_by_production.values():
            runtime.workers = refreshed_registry
        return worker

    def workers(self) -> tuple[ProductionWorker, ...]:
        return tuple(self._workers[key] for key in sorted(self._workers))

    def refresh_readiness(self, production_id: str) -> ProductionTaskGraphRefreshResult:
        normalized = self._require_production_id(production_id)
        repository = self._task_repository()
        return ProductionTaskGraphIntegrationService(
            repository,
            ProductionTaskLifecycleService(repository),
        ).refresh(normalized)

    def production_readiness(self, production_id: str) -> ProductionReadinessAssessment:
        """Return the integrated read-only readiness assessment for one production."""
        normalized = self._require_production_id(production_id)
        return ProductionReadinessIntegrationService(
            self._task_repository(),
            self._schedule_repository(),
        ).assess(
            normalized,
            queue=self._queues.get(normalized),
            resources=self.resources(),
            workers=self.workers(),
        )

    def create_schedule_revision(self, production_id: str) -> ProductionScheduleSnapshot:
        normalized = self._require_production_id(production_id)
        scheduling = ProductionSchedulingService(
            self._task_repository(),
            ProductionResourceCatalog(self.resources()),
        )
        return ProductionSchedulePersistenceService(
            scheduling,
            self._schedule_repository(),
        ).create_revision(normalized)

    def latest_schedule(self, production_id: str) -> ProductionScheduleSnapshot | None:
        return self._schedule_repository().latest_for_production(
            self._require_production_id(production_id)
        )

    def review_view(self, production_id: str) -> ProductionScheduleReviewView | None:
        snapshot = self.latest_schedule(production_id)
        if snapshot is None:
            return None
        return ProductionScheduleReviewService(self._schedule_repository()).view(
            snapshot.schedule_id,
            snapshot.revision,
        )

    def review_current(
        self,
        production_id: str,
        *,
        decision: ProductionScheduleReviewDecision,
        reviewed_by: str,
        notes: str,
    ) -> ProductionScheduleReviewRecord:
        snapshot = self.latest_schedule(production_id)
        if snapshot is None:
            raise ProductionSchedulingUiError("No ProductionSchedule exists for review")
        return ProductionScheduleReviewService(self._schedule_repository()).review(
            snapshot.schedule_id,
            snapshot.revision,
            decision=decision,
            reviewed_by=reviewed_by,
            notes=notes,
        )

    def compile_queue(self, production_id: str) -> ProductionQueue:
        normalized = self._require_production_id(production_id)
        queue = ProductionQueueCompilerService(
            self._schedule_repository(),
            self._task_repository(),
        ).compile(normalized)
        self._queues[normalized] = queue
        self._runtime_by_production[normalized] = ProductionQueueRuntimeService(
            self._task_repository(),
            self._worker_registry,
        )
        return queue

    def queue(self, production_id: str) -> ProductionQueue | None:
        return self._queues.get(self._require_production_id(production_id))

    def monitoring(self, production_id: str) -> ProductionSchedulingMonitoringSnapshot | None:
        normalized = self._require_production_id(production_id)
        queue = self._queues.get(normalized)
        if queue is None:
            return None
        return self._monitor.snapshot(queue, workers=self.workers())

    def recover(self, production_id: str) -> ProductionSchedulingRecoveryResult:
        normalized = self._require_production_id(production_id)
        queue = self._queues.get(normalized)
        if queue is None:
            raise ProductionSchedulingUiError("No ProductionQueue exists for recovery")
        runtime = self._runtime(normalized)
        result = ProductionSchedulingRecoveryService(runtime).recover_expired(queue)
        self._queues[normalized] = result.queue
        return result

    def _runtime(self, production_id: str) -> ProductionQueueRuntimeService:
        runtime = self._runtime_by_production.get(production_id)
        if runtime is None:
            runtime = ProductionQueueRuntimeService(
                self._task_repository(),
                self._worker_registry,
            )
            self._runtime_by_production[production_id] = runtime
        return runtime

    def _task_repository(self) -> ProductionTaskRepository:
        return self._task_repository_factory()

    def _schedule_repository(self) -> ProductionScheduleRepository:
        return self._schedule_repository_factory()

    @staticmethod
    def _require_production_id(production_id: str) -> str:
        normalized = production_id.strip()
        if not normalized:
            raise ProductionSchedulingUiError("production_id cannot be blank")
        return normalized


def _same_compiled_contract(existing: ProductionTask, candidate: ProductionTask) -> bool:
    """Compare immutable compiled authority while ignoring lifecycle state/timestamps."""
    return (
        existing.task_id == candidate.task_id
        and existing.production_id == candidate.production_id
        and existing.episode_id == candidate.episode_id
        and existing.scene_id == candidate.scene_id
        and existing.shot_id == candidate.shot_id
        and existing.task_type is candidate.task_type
        and existing.authority == candidate.authority
        and existing.capabilities == candidate.capabilities
        and existing.expected_outputs == candidate.expected_outputs
        and existing.dependencies == candidate.dependencies
        and existing.required_inputs == candidate.required_inputs
        and existing.priority is candidate.priority
        and existing.attempt_policy == candidate.attempt_policy
        and existing.provenance == candidate.provenance
        and existing.metadata == candidate.metadata
    )