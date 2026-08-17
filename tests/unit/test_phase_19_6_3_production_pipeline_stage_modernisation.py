"""Focused regression tests for Phase 19.6.3 pipeline-stage modernisation."""

from datetime import UTC, datetime

import pytest

from vscs.application.production_pipeline import (
    ProductionNode,
    ProductionPipeline,
    ProductionStage,
    ProductionState,
    RenderQueueEntry,
)
from vscs.application.production_tasks import (
    PRODUCTION_TASK_ID_METADATA_KEY,
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskLegacyBridge,
    ProductionTaskLifecycleService,
    ProductionTaskStageService,
    ProductionTaskState,
    ProductionTaskTransitionError,
    ProductionTaskType,
)
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository


def _task(*, state: ProductionTaskState = ProductionTaskState.PLANNED) -> ProductionTask:
    return ProductionTask(
        task_id="PT-VIDEO-GENERATION-ABC123",
        production_id="PROD-001",
        episode_id="EP-001",
        scene_id="SC-001",
        shot_id="SH-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SH-001",
            revision=1,
            fingerprint="fingerprint-001",
            approved=True,
            approved_by="tester",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=state,
        created_at=datetime(2026, 8, 17, 12, 0, tzinfo=UTC),
    )


def _node(pipeline: ProductionPipeline, node_id: str) -> ProductionNode:
    node = pipeline.node(node_id)
    assert node is not None
    return node


def test_stage_service_enforces_provider_neutral_lifecycle() -> None:
    service = ProductionTaskStageService()
    ready, transition = service.transition(
        _task(),
        ProductionTaskState.READY,
        now=datetime(2026, 8, 17, 12, 1, tzinfo=UTC),
    )

    assert ready.state is ProductionTaskState.READY
    assert transition.previous_state is ProductionTaskState.PLANNED
    assert transition.current_state is ProductionTaskState.READY

    running, _ = service.transition(ready, ProductionTaskState.RUNNING)
    completed, _ = service.transition(running, ProductionTaskState.COMPLETED)
    assert completed.state is ProductionTaskState.COMPLETED


def test_stage_service_rejects_invalid_direct_execution_transition() -> None:
    with pytest.raises(ProductionTaskTransitionError):
        ProductionTaskStageService().transition(
            _task(),
            ProductionTaskState.RUNNING,
        )


def test_json_repository_round_trips_authoritative_task(tmp_path) -> None:
    repository = JsonProductionTaskRepository(tmp_path / "production_tasks")
    original = _task()

    repository.save(original)

    assert repository.get(original.task_id) == original
    assert repository.list_for_production("PROD-001") == (original,)


def test_lifecycle_service_persists_transitions(tmp_path) -> None:
    repository = JsonProductionTaskRepository(tmp_path / "production_tasks")
    lifecycle = ProductionTaskLifecycleService(repository)
    original = lifecycle.register(_task())

    ready, _ = lifecycle.transition(original.task_id, ProductionTaskState.READY)

    assert ready.state is ProductionTaskState.READY
    assert repository.get(original.task_id) == ready


def test_legacy_bridge_binds_queue_without_replacing_legacy_contract() -> None:
    bridge = ProductionTaskLegacyBridge()
    entry = RenderQueueEntry(
        entry_id="QUEUE-001",
        job_id="JOB-001",
        clip_id="SH-001",
    )

    bound = bridge.bind_queue_entry(entry, _task())

    assert entry.metadata == ()
    assert dict(bound.metadata)[PRODUCTION_TASK_ID_METADATA_KEY] == _task().task_id
    assert bridge.task_id_for_entry(bound) == _task().task_id


def test_legacy_pipeline_is_only_a_projection_of_task_state() -> None:
    bridge = ProductionTaskLegacyBridge()
    pipeline = ProductionPipeline(
        pipeline_id="PIPE-001",
        production_id="PROD-001",
        episode_id="EP-001",
        nodes=(
            ProductionNode(
                node_id="PREP-001",
                stage=ProductionStage.BUNDLE_VALIDATION,
                state=ProductionState.COMPLETED,
                clip_id="SH-001",
            ),
            ProductionNode(
                node_id="RENDER-001",
                stage=ProductionStage.RENDERING,
                state=ProductionState.PENDING,
                clip_id="SH-001",
            ),
        ),
    )

    projected = bridge.reconcile_pipeline(
        pipeline,
        _task(state=ProductionTaskState.RUNNING),
        clip_id="SH-001",
    )

    assert _node(pipeline, "RENDER-001").state is ProductionState.PENDING
    assert _node(projected, "RENDER-001").state is ProductionState.RUNNING
    assert _node(projected, "PREP-001").state is ProductionState.COMPLETED
