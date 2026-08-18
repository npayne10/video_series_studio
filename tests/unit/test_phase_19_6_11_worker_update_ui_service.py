"""Focused validation for Phase 19.6.11 session worker updates."""

from vscs.application.production_tasks import (
    ProductionCapability,
    ProductionSchedulingUiService,
    ProductionWorker,
    ProductionWorkerState,
)
from vscs.infrastructure.production.schedule_repository import JsonProductionScheduleRepository
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository


def test_existing_session_worker_can_be_updated_without_new_identity(tmp_path) -> None:
    service = ProductionSchedulingUiService(
        lambda: JsonProductionTaskRepository(tmp_path / "tasks"),
        lambda: JsonProductionScheduleRepository(tmp_path / "schedules"),
    )
    unavailable = ProductionWorker(
        worker_id="LOCAL-WORKER-01",
        resource_id="LOCAL-GPU-01",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        state=ProductionWorkerState.UNAVAILABLE,
    )
    available = ProductionWorker(
        worker_id="LOCAL-WORKER-01",
        resource_id="LOCAL-GPU-01",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        state=ProductionWorkerState.AVAILABLE,
    )

    service.register_worker(unavailable)
    service.register_worker(available)

    assert service.workers() == (available,)
