"""Integration coverage for Phase 19.6.12 Production Readiness Integration."""

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


def test_persisted_authority_to_runtime_preparation_reports_ready(tmp_path) -> None:
    task_root = tmp_path / "project" / "production" / "scheduling" / "tasks"
    schedule_root = tmp_path / "project" / "production" / "scheduling" / "schedules"
    service = ProductionSchedulingUiService(
        lambda: JsonProductionTaskRepository(task_root),
        lambda: JsonProductionScheduleRepository(schedule_root),
    )
    task = ProductionTask(
        task_id="PT-READINESS-E2E-001",
        production_id="PROD-READINESS-E2E",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-READINESS-E2E-001",
            revision=1,
            fingerprint="readiness-e2e-authority",
            approved=True,
            approved_by="operator",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=ProductionTaskState.PLANNED,
        created_at=datetime(2026, 8, 18, 14, 45, tzinfo=UTC),
    )

    service.register_compiled_tasks((task,))
    service.register_resource(
        ProductionResource(
            resource_id="LOCAL-GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    service.register_worker(
        ProductionWorker(
            worker_id="LOCAL-WORKER-01",
            resource_id="LOCAL-GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    service.refresh_readiness("PROD-READINESS-E2E")
    service.create_schedule_revision("PROD-READINESS-E2E")
    service.review_current(
        "PROD-READINESS-E2E",
        decision=ProductionScheduleReviewDecision.APPROVED,
        reviewed_by="operator",
        notes="Production readiness integration acceptance path.",
    )
    service.compile_queue("PROD-READINESS-E2E")

    assessment = service.production_readiness("PROD-READINESS-E2E")

    assert assessment.status is ProductionReadinessStatus.READY
    assert assessment.ready
    assert assessment.task_count == 1
    assert assessment.scheduled_count == 1
    assert assessment.queue_entry_count == 1
    assert assessment.executable_entry_count == 1
    assert {finding.code for finding in assessment.findings} == {
        ProductionReadinessCode.READY_FOR_EXECUTION
    }
