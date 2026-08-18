"""Application facade used by the Production Scheduling workspace."""

from __future__ import annotations

from pathlib import Path

from vscs.application.projects import ProjectService
from vscs.infrastructure.production.schedule_repository import JsonProductionScheduleRepository
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository

from .graph import ProductionTaskGraphIntegrationService, ProductionTaskGraphRefreshResult
from .lifecycle import ProductionTaskLifecycleService
from .models import ProductionTask
from .production_queue import ProductionQueue, ProductionQueueCompilerService
from .resources import ProductionResource, ProductionResourceCatalog
from .runtime import ProductionQueueRuntimeService, ProductionWorker, ProductionWorkerRegistry
from .schedule_records import (
    ProductionSchedulePersistenceService,
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


class ProductionSchedulingUiService:
    """Thin application facade for operator-facing scheduling commands and queries.

    Durable task/schedule authority is project-scoped. Resource and worker registration
    remains session-scoped because Phase 19.6 has not yet introduced resource discovery
    or persistence.
    """

    def __init__(self, projects: ProjectService) -> None:
        self.projects = projects
        self._resources: dict[str, ProductionResource] = {}
        self._workers: dict[str, ProductionWorker] = {}
        self._worker_registry = ProductionWorkerRegistry()
        self._queues: dict[str, ProductionQueue] = {}
        self._runtime_by_production: dict[str, ProductionQueueRuntimeService] = {}
        self._monitor = ProductionSchedulingMonitor()

    def register_compiled_tasks(self, tasks: tuple[ProductionTask, ...]) -> tuple[ProductionTask, ...]:
        """Persist compiler output without changing task lifecycle state."""
        repository = self._task_repository()
        lifecycle = ProductionTaskLifecycleService(repository)
        for task in tasks:
            lifecycle.register(task)
        return tasks

    def tasks(self, production_id: str) -> tuple[ProductionTask, ...]:
        return self._task_repository().list_for_production(self._require_production_id(production_id))

    def register_resource(self, resource: ProductionResource) -> ProductionResource:
        self._resources[resource.resource_id] = resource
        return resource

    def resources(self) -> tuple[ProductionResource, ...]:
        return tuple(self._resources[key] for key in sorted(self._resources))

    def register_worker(self, worker: ProductionWorker) -> ProductionWorker:
        existing = self._workers.get(worker.worker_id)
        if existing is not None:
            raise ProductionSchedulingUiError(f"ProductionWorker already registered: {worker.worker_id}")
        self._worker_registry.register(worker)
        self._workers[worker.worker_id] = worker
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
        runtime = self._runtime(normalized)
        return self._monitor.snapshot(
            queue,
            workers=self.workers(),
            leases=tuple(runtime.leases.active_leases(now=None)),
        )

    def recover(self, production_id: str) -> ProductionSchedulingRecoveryResult:
        normalized = self._require_production_id(production_id)
        queue = self._queues.get(normalized)
        if queue is None:
            raise ProductionSchedulingUiError("No ProductionQueue exists for recovery")
        runtime = self._runtime(normalized)
        result = ProductionSchedulingRecoveryService(runtime).recover(queue)
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

    def _task_repository(self) -> JsonProductionTaskRepository:
        root = self._production_root() / "tasks"
        return JsonProductionTaskRepository(root)

    def _schedule_repository(self) -> JsonProductionScheduleRepository:
        root = self._production_root() / "schedules"
        return JsonProductionScheduleRepository(root)

    def _production_root(self) -> Path:
        project_directory = self.projects.project_directory
        if project_directory is None:
            raise ProductionSchedulingUiError("Open a VSCS project before using Production Scheduling")
        return project_directory / "production" / "scheduling"

    @staticmethod
    def _require_production_id(production_id: str) -> str:
        normalized = production_id.strip()
        if not normalized:
            raise ProductionSchedulingUiError("production_id cannot be blank")
        return normalized
