"""Focused tests for Phase 20.3 provider execution contract modernisation."""

from datetime import UTC, datetime, timedelta

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionExecutionLease,
    ProductionQueue,
    ProductionQueueAttempt,
    ProductionQueueEntry,
    ProductionQueueState,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.provider_execution import (
    ProviderExecutionBindingError,
    ProviderExecutionContextFactory,
    ProviderExecutionPayloadKind,
    ProviderExecutionState,
)

NOW = datetime(2026, 8, 18, 17, 0, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-001",
        production_id="PROD-001",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-001",
            revision=1,
            fingerprint="authority-fingerprint",
            approved=True,
            approved_by="reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video",),
        state=ProductionTaskState.READY,
    )


def _queue(state: ProductionQueueState = ProductionQueueState.RUNNING) -> ProductionQueue:
    attempts = ()
    claimed_by = None
    if state is ProductionQueueState.RUNNING:
        attempts = (
            ProductionQueueAttempt(
                attempt_number=1,
                worker_id="WORKER-01",
                started_at=NOW,
            ),
        )
        claimed_by = "WORKER-01"
    elif state is ProductionQueueState.CLAIMED:
        claimed_by = "WORKER-01"
    return ProductionQueue(
        queue_id="PQ-001",
        production_id="PROD-001",
        schedule_id="SCHED-001",
        schedule_revision=1,
        schedule_fingerprint="schedule-fingerprint",
        entries=(
            ProductionQueueEntry(
                entry_id="PQE-PT-001",
                task_id="PT-001",
                resource_id="GPU-01",
                task_type=ProductionTaskType.VIDEO_GENERATION,
                state=state,
                priority=ProductionTaskPriority.NORMAL,
                attempts=attempts,
                claimed_by=claimed_by,
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
    )


def _lease() -> ProductionExecutionLease:
    return ProductionExecutionLease(
        lease_id="LEASE-001",
        queue_id="PQ-001",
        entry_id="PQE-PT-001",
        task_id="PT-001",
        worker_id="WORKER-01",
        acquired_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        last_heartbeat_at=NOW,
    )


def test_context_binds_running_queue_attempt_and_lease() -> None:
    context = ProviderExecutionContextFactory().bind(
        _queue(), "PQE-PT-001", _lease(), _task()
    )

    assert context.execution_id == "PEX-PQ-001-PQE-PT-001-A001"
    assert context.task_id == "PT-001"
    assert context.worker_id == "WORKER-01"
    assert context.lease_id == "LEASE-001"
    assert context.attempt_number == 1
    assert context.required_capabilities == (ProductionCapability.VIDEO_GENERATION,)
    assert context.authority_fingerprint == "authority-fingerprint"


def test_context_rejects_claimed_entry_before_attempt_start() -> None:
    with pytest.raises(ProviderExecutionBindingError, match="RUNNING"):
        ProviderExecutionContextFactory().bind(
            _queue(ProductionQueueState.CLAIMED), "PQE-PT-001", _lease(), _task()
        )


def test_context_rejects_mismatched_lease_ownership() -> None:
    lease = ProductionExecutionLease(
        lease_id="LEASE-OTHER",
        queue_id="PQ-OTHER",
        entry_id="PQE-PT-001",
        task_id="PT-001",
        worker_id="WORKER-01",
        acquired_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        last_heartbeat_at=NOW,
    )

    with pytest.raises(ProviderExecutionBindingError, match="does not own"):
        ProviderExecutionContextFactory().bind(
            _queue(), "PQE-PT-001", lease, _task()
        )


def test_provider_execution_payload_kind_is_provider_neutral() -> None:
    assert ProviderExecutionPayloadKind.RENDER.value == "render"


def test_provider_execution_states_cover_existing_render_lifecycle() -> None:
    assert {state.value for state in ProviderExecutionState} == {
        "queued",
        "preparing",
        "running",
        "completed",
        "failed",
        "cancelled",
        "retrying",
    }
