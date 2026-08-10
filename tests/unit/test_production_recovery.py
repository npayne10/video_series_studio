"""Tests for Phase 14.5 production recovery."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from vscs.application.production_pipeline import (
    ExecutionLease,
    OutputObservation,
    OutputStatus,
    ProductionNode,
    ProductionPipeline,
    ProductionRecoveryConfig,
    ProductionRecoveryEngine,
    ProductionStage,
    ProductionState,
    QueueAttempt,
    QueueState,
    RecoveryAction,
    RecoveryReason,
    RenderQueue,
    RenderQueueEntry,
)

NOW = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


def _pipeline(state: ProductionState = ProductionState.RUNNING) -> ProductionPipeline:
    return ProductionPipeline(
        pipeline_id="PIPELINE-001",
        production_id="PRODUCTION-001",
        episode_id="EPISODE-001",
        nodes=(
            ProductionNode(
                node_id="RENDER-001",
                stage=ProductionStage.RENDERING,
                state=state,
                clip_id="CLIP-001",
            ),
        ),
    )


def _queue_entry(
    *,
    state: QueueState = QueueState.RUNNING,
    attempts: tuple[QueueAttempt, ...] = (),
    maximum_attempts: int = 3,
    claimed_by: str | None = "worker-a",
    updated_at: datetime = NOW,
) -> RenderQueueEntry:
    return RenderQueueEntry(
        entry_id="Q-001",
        job_id="JOB-001",
        clip_id="CLIP-001",
        state=state,
        maximum_attempts=maximum_attempts,
        attempts=attempts,
        claimed_by=claimed_by,
        created_at=NOW - timedelta(minutes=10),
        updated_at=updated_at,
    )


def _queue(entry: RenderQueueEntry) -> RenderQueue:
    return RenderQueue(
        queue_id="QUEUE-001",
        pipeline_id="PIPELINE-001",
        entries=(entry,),
    )


def _lease(*, expires_at: datetime) -> ExecutionLease:
    return ExecutionLease(
        lease_id="LEASE-001",
        worker_id="worker-a",
        job_id="JOB-001",
        acquired_at=NOW - timedelta(minutes=5),
        expires_at=expires_at,
        last_heartbeat_at=NOW - timedelta(minutes=2),
    )


def test_expired_lease_retries_claimed_entry() -> None:
    entry = _queue_entry(state=QueueState.CLAIMED, attempts=(), maximum_attempts=2)
    result = ProductionRecoveryEngine().reconcile(
        _pipeline(),
        _queue(entry),
        leases=(_lease(expires_at=NOW - timedelta(seconds=1)),),
        active_worker_ids=frozenset({"worker-a"}),
        now=NOW,
    )

    recovered = result.queue.entry("Q-001")
    assert recovered is not None
    assert recovered.state is QueueState.READY
    assert recovered.claimed_by is None
    assert result.decisions[0].action is RecoveryAction.RETRY
    assert result.decisions[0].reason is RecoveryReason.EXPIRED_LEASE
    assert result.pipeline.nodes[0].state is ProductionState.READY


def test_abandoned_claim_is_released_after_threshold() -> None:
    entry = _queue_entry(
        state=QueueState.CLAIMED,
        attempts=(),
        claimed_by="worker-missing",
        updated_at=NOW - timedelta(minutes=10),
    )
    engine = ProductionRecoveryEngine(ProductionRecoveryConfig(abandon_claim_after_seconds=60))

    result = engine.reconcile(_pipeline(), _queue(entry), now=NOW)

    assert result.decisions[0].reason is RecoveryReason.ABANDONED_CLAIM
    assert result.queue.entry("Q-001").state is QueueState.READY


def test_interrupted_running_attempt_is_closed_and_retried() -> None:
    attempt = QueueAttempt(
        attempt_number=1,
        worker_id="worker-a",
        started_at=NOW - timedelta(minutes=3),
    )
    entry = _queue_entry(attempts=(attempt,), maximum_attempts=3)

    result = ProductionRecoveryEngine().reconcile(
        _pipeline(),
        _queue(entry),
        leases=(_lease(expires_at=NOW - timedelta(seconds=1)),),
        now=NOW,
    )

    recovered = result.queue.entry("Q-001")
    assert recovered is not None
    assert recovered.attempts[0].completed_at == NOW
    assert recovered.attempts[0].succeeded is False
    assert recovered.attempts[0].error_message == "Execution interrupted during recovery"
    assert result.decisions[0].reason is RecoveryReason.INTERRUPTED_WORKER


def test_existing_output_marks_entry_complete() -> None:
    entry = _queue_entry(state=QueueState.READY, attempts=(), claimed_by=None)
    output = OutputObservation(
        job_id="JOB-001",
        status=OutputStatus.PRESENT,
        output_path="renders/clip-001.mp4",
        checksum="abc123",
    )

    result = ProductionRecoveryEngine().reconcile(
        _pipeline(ProductionState.READY),
        _queue(entry),
        outputs=(output,),
        now=NOW,
    )

    assert result.queue.entry("Q-001").state is QueueState.COMPLETED
    assert result.pipeline.nodes[0].state is ProductionState.COMPLETED
    assert result.decisions[0].action is RecoveryAction.COMPLETE
    assert result.decisions[0].reason is RecoveryReason.OUTPUT_PRESENT


def test_missing_completed_output_retries_or_fails_when_exhausted() -> None:
    attempt = QueueAttempt(
        attempt_number=1,
        worker_id="worker-a",
        started_at=NOW - timedelta(minutes=2),
        completed_at=NOW - timedelta(minutes=1),
        succeeded=True,
    )
    missing = OutputObservation(job_id="JOB-001", status=OutputStatus.MISSING)
    retry_entry = _queue_entry(
        state=QueueState.COMPLETED,
        attempts=(attempt,),
        maximum_attempts=2,
        claimed_by=None,
    )

    retried = ProductionRecoveryEngine().reconcile(
        _pipeline(ProductionState.COMPLETED),
        _queue(retry_entry),
        outputs=(missing,),
        now=NOW,
    )
    assert retried.queue.entry("Q-001").state is QueueState.READY
    assert retried.decisions[0].reason is RecoveryReason.MISSING_OUTPUT

    exhausted_entry = replace(retry_entry, maximum_attempts=1)
    failed = ProductionRecoveryEngine().reconcile(
        _pipeline(ProductionState.COMPLETED),
        _queue(exhausted_entry),
        outputs=(missing,),
        now=NOW,
    )
    assert failed.queue.entry("Q-001").state is QueueState.FAILED
    assert failed.decisions[0].action is RecoveryAction.FAIL
    assert failed.decisions[0].reason is RecoveryReason.ATTEMPTS_EXHAUSTED


def test_manual_recovery_is_audited_and_reconciles_pipeline() -> None:
    entry = _queue_entry(state=QueueState.FAILED, claimed_by=None)
    engine = ProductionRecoveryEngine()

    reset = engine.apply_manual(
        _pipeline(ProductionState.FAILED),
        _queue(entry),
        "Q-001",
        RecoveryAction.RESET,
        message="Operator approved retry",
        now=NOW,
    )

    assert reset.queue.entry("Q-001").state is QueueState.READY
    assert reset.pipeline.nodes[0].state is ProductionState.READY
    assert reset.decisions[0].automatic is False
    assert reset.decisions[0].reason is RecoveryReason.MANUAL_ACTION
    assert reset.events[0].automatic is False
    assert reset.events[0].message == "Operator approved retry"
