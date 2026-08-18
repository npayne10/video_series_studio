"""Focused tests for Phase 19.6.12 Production Readiness Integration."""

from datetime import UTC, datetime

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionReadinessCode,
    ProductionReadinessStatus,
    ProductionResource,
    ProductionScheduleReviewDecision,
    ProductionSchedulingUiService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
)
from vscs.infrastructure.production.schedule_repository import JsonProductionScheduleRepository
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository

_NOW = datetime(2026, 8, 18, 14, 30, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-READINESS-INTEGRATION-001",
        production_id="PROD-READINESS-INTEGRATION",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-READINESS-INTEGRATION-001",
            revision=1,
            fingerprint="readiness-integration-authority",
            approved=True,
            approved_by="planner",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=ProductionTaskState.PLANNED,
        created_at=_NOW,
    )


def _service(tmp_path) -> ProductionSchedulingUiService:
    return ProductionSchedulingUiService(
        lambda: JsonProductionTaskRepository(tmp_path / "tasks"),
        lambda: JsonProductionScheduleRepository(tmp_path / "schedules"),
    )


def _codes(assessment) -> set[ProductionReadinessCode]:
    return {finding.code for finding in assessment.findings}


def test_readiness_is_not_ready_without_authoritative_tasks(tmp_path) -> None:
    service = _service(tmp_path)

    assessment = service.production_readiness("PROD-READINESS-INTEGRATION")

    assert assessment.status is ProductionReadinessStatus.NOT_READY
    assert ProductionReadinessCode.NO_TASKS in _codes(assessment)
    assert assessment.task_count == 0


def test_readiness_reports_missing_schedule_for_planned_work(tmp_path) -> None:
    service = _service(tmp_path)
    service.register_compiled_tasks((_task(),))

    assessment = service.production_readiness("PROD-READINESS-INTEGRATION")

    assert assessment.status is ProductionReadinessStatus.NOT_READY
    assert ProductionReadinessCode.TASKS_NOT_READY in _codes(assessment)
    assert ProductionReadinessCode.NO_SCHEDULE in _codes(assessment)


def test_approved_queue_is_blocked_until_matching_worker_is_available(tmp_path) -> None:
    service = _service(tmp_path)
    service.register_resource(
        ProductionResource(
            resource_id="GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    service.register_compiled_tasks((_task(),))
    service.refresh_readiness("PROD-READINESS-INTEGRATION")
    service.create_schedule_revision("PROD-READINESS-INTEGRATION")
    service.review_current(
        "PROD-READINESS-INTEGRATION",
        decision=ProductionScheduleReviewDecision.APPROVED,
        reviewed_by="operator",
        notes="Approved for readiness integration validation.",
    )
    service.compile_queue("PROD-READINESS-INTEGRATION")

    assessment = service.production_readiness("PROD-READINESS-INTEGRATION")

    assert assessment.status is ProductionReadinessStatus.BLOCKED
    assert ProductionReadinessCode.WORKER_NOT_REGISTERED in _codes(assessment)
    assert assessment.queue_entry_count == 1
    assert assessment.executable_entry_count == 1


def test_ready_requires_tasks_approved_schedule_queue_resource_and_worker(tmp_path) -> None:
    service = _service(tmp_path)
    service.register_resource(
        ProductionResource(
            resource_id="GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    service.register_worker(
        ProductionWorker(
            worker_id="WORKER-01",
            resource_id="GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    service.register_compiled_tasks((_task(),))
    service.refresh_readiness("PROD-READINESS-INTEGRATION")
    service.create_schedule_revision("PROD-READINESS-INTEGRATION")
    service.review_current(
        "PROD-READINESS-INTEGRATION",
        decision=ProductionScheduleReviewDecision.APPROVED,
        reviewed_by="operator",
        notes="All production authorities reviewed.",
    )
    service.compile_queue("PROD-READINESS-INTEGRATION")

    assessment = service.production_readiness("PROD-READINESS-INTEGRATION")

    assert assessment.status is ProductionReadinessStatus.READY
    assert assessment.ready
    assert _codes(assessment) == {ProductionReadinessCode.READY_FOR_EXECUTION}
    assert assessment.task_count == 1
    assert assessment.scheduled_count == 1
    assert assessment.queue_entry_count == 1
    assert assessment.executable_entry_count == 1
