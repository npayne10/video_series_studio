"""Functional acceptance coverage for the complete Phase 19.6 production scheduling chain."""

from datetime import UTC, datetime, timedelta

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueueError,
    ProductionQueueRuntimeService,
    ProductionQueueState,
    ProductionReadinessCode,
    ProductionReadinessStatus,
    ProductionResource,
    ProductionScheduleReviewDecision,
    ProductionSchedulingMonitor,
    ProductionSchedulingRecoveryService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
    ProductionWorkerRegistry,
    SchedulingRecoveryAction,
)
from vscs.application.production_tasks.ui_service import ProductionSchedulingUiService
from vscs.infrastructure.production.schedule_repository import JsonProductionScheduleRepository
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository

_NOW = datetime(2026, 8, 18, 15, 0, tzinfo=UTC)
_PRODUCTION_ID = "PROD-19-6-13"
_RESOURCE_ID = "LOCAL-GPU-01"
_WORKER_ID = "LOCAL-WORKER-01"


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-19-6-13-VIDEO-001",
        production_id=_PRODUCTION_ID,
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SHT-001",
            revision=1,
            fingerprint="phase-19-6-13-authority",
            approved=True,
            approved_by="acceptance-operator",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=ProductionTaskState.PLANNED,
        created_at=_NOW,
    )


def _resource() -> ProductionResource:
    return ProductionResource(
        resource_id=_RESOURCE_ID,
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
    )


def _worker() -> ProductionWorker:
    return ProductionWorker(
        worker_id=_WORKER_ID,
        resource_id=_RESOURCE_ID,
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
    )


def _service(tmp_path):
    task_root = tmp_path / "project" / "production" / "scheduling" / "tasks"
    schedule_root = tmp_path / "project" / "production" / "scheduling" / "schedules"
    service = ProductionSchedulingUiService(
        lambda: JsonProductionTaskRepository(task_root),
        lambda: JsonProductionScheduleRepository(schedule_root),
    )
    return service, task_root


def _prepare_approved_queue(service: ProductionSchedulingUiService):
    service.register_compiled_tasks((_task(),))
    service.register_resource(_resource())

    refresh = service.refresh_readiness(_PRODUCTION_ID)
    assert refresh.tasks[0].state is ProductionTaskState.READY

    schedule = service.create_schedule_revision(_PRODUCTION_ID)
    assert len(schedule.schedule.assignments) == 1
    assert schedule.schedule.assignments[0].resource_id == _RESOURCE_ID

    with pytest.raises(ProductionQueueError):
        service.compile_queue(_PRODUCTION_ID)

    service.review_current(
        _PRODUCTION_ID,
        decision=ProductionScheduleReviewDecision.APPROVED,
        reviewed_by="acceptance-operator",
        notes="Phase 19.6.13 functional acceptance.",
    )
    return service.compile_queue(_PRODUCTION_ID)


def test_governed_chain_requires_worker_before_integrated_readiness(tmp_path) -> None:
    service, _task_root = _service(tmp_path)
    queue = _prepare_approved_queue(service)

    blocked = service.production_readiness(_PRODUCTION_ID)
    assert blocked.status is ProductionReadinessStatus.BLOCKED
    assert ProductionReadinessCode.WORKER_NOT_REGISTERED in {
        finding.code for finding in blocked.findings
    }

    service.register_worker(_worker())
    ready = service.production_readiness(_PRODUCTION_ID)

    assert ready.status is ProductionReadinessStatus.READY
    assert ready.ready
    assert ready.task_count == 1
    assert ready.scheduled_count == 1
    assert ready.queue_entry_count == 1
    assert ready.executable_entry_count == 1
    assert queue.entries[0].state is ProductionQueueState.READY


def test_runtime_claim_start_heartbeat_monitor_and_complete(tmp_path) -> None:
    service, task_root = _service(tmp_path)
    queue = _prepare_approved_queue(service)
    worker = _worker()
    service.register_worker(worker)

    registry = ProductionWorkerRegistry()
    registry.register(worker)
    runtime = ProductionQueueRuntimeService(
        JsonProductionTaskRepository(task_root),
        registry,
    )
    entry = queue.entries[0]

    claim = runtime.claim(
        queue,
        entry.entry_id,
        worker.worker_id,
        lease_duration_seconds=30,
        now=_NOW,
    )
    assert claim.queue.entry(entry.entry_id).state is ProductionQueueState.CLAIMED  # type: ignore[union-attr]

    running = runtime.start(
        claim.queue,
        entry.entry_id,
        claim.lease.lease_id,
        now=_NOW + timedelta(seconds=1),
    )
    renewed = runtime.heartbeat(
        running,
        entry.entry_id,
        claim.lease.lease_id,
        duration_seconds=30,
        now=_NOW + timedelta(seconds=2),
    )
    assert renewed.expires_at == _NOW + timedelta(seconds=32)

    monitor = ProductionSchedulingMonitor().snapshot(
        running,
        workers=(worker,),
        leases=(renewed,),
        now=_NOW + timedelta(seconds=3),
    )
    assert monitor.progress.running == 1
    assert monitor.workers[0].active_entry_id == entry.entry_id
    assert not monitor.diagnostics

    completed = runtime.complete(
        running,
        entry.entry_id,
        renewed.lease_id,
        now=_NOW + timedelta(seconds=4),
    )
    completed_snapshot = ProductionSchedulingMonitor().snapshot(
        completed,
        workers=(worker,),
        now=_NOW + timedelta(seconds=4),
    )
    assert completed_snapshot.progress.completed == 1
    assert completed_snapshot.progress.completion_percentage == 100.0


def test_expired_running_lease_routes_through_retry_recovery(tmp_path) -> None:
    service, task_root = _service(tmp_path)
    queue = _prepare_approved_queue(service)
    worker = _worker()

    registry = ProductionWorkerRegistry()
    registry.register(worker)
    runtime = ProductionQueueRuntimeService(
        JsonProductionTaskRepository(task_root),
        registry,
    )
    entry = queue.entries[0]

    claim = runtime.claim(
        queue,
        entry.entry_id,
        worker.worker_id,
        lease_duration_seconds=5,
        now=_NOW,
    )
    running = runtime.start(
        claim.queue,
        entry.entry_id,
        claim.lease.lease_id,
        now=_NOW + timedelta(seconds=1),
    )

    before_recovery = ProductionSchedulingMonitor().snapshot(
        running,
        workers=(worker,),
        leases=(claim.lease,),
        now=_NOW + timedelta(seconds=6),
    )
    assert "EXECUTION_LEASE_EXPIRED" in {
        diagnostic.code for diagnostic in before_recovery.diagnostics
    }

    result = ProductionSchedulingRecoveryService(runtime).recover_expired(
        running,
        now=_NOW + timedelta(seconds=6),
    )

    assert len(result.decisions) == 1
    assert result.decisions[0].action is SchedulingRecoveryAction.RETRY
    assert len(result.events) == 1
    recovered_entry = result.queue.entry(entry.entry_id)
    assert recovered_entry is not None
    assert recovered_entry.state is ProductionQueueState.READY
    assert recovered_entry.attempt_count == 1
