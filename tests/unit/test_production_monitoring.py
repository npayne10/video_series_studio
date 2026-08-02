"""Tests for Phase 14.4 production monitoring."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from vscs.application.acpp import RenderCapability
from vscs.application.production_pipeline import (
    ExecutionResult,
    ExecutorErrorCode,
    LeaseManager,
    ProductionEvent,
    ProductionMonitor,
    ProductionMonitoringConfig,
    ProductionNode,
    ProductionPipeline,
    ProductionStage,
    ProductionState,
    QueueState,
    RenderQueue,
    RenderQueueEntry,
    WorkerHealth,
    WorkerIdentity,
    WorkerObservation,
)

NOW = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


def _pipeline() -> ProductionPipeline:
    return ProductionPipeline(
        pipeline_id="PIPELINE-001",
        production_id="PROD-001",
        episode_id="E01",
        nodes=(
            ProductionNode(
                node_id="N-001",
                stage=ProductionStage.RENDERING,
                state=ProductionState.COMPLETED,
            ),
            ProductionNode(
                node_id="N-002",
                stage=ProductionStage.QUALITY_CONTROL,
                state=ProductionState.RUNNING,
                dependencies=("N-001",),
            ),
        ),
    )


def _queue() -> RenderQueue:
    return RenderQueue(
        queue_id="QUEUE-001",
        pipeline_id="PIPELINE-001",
        entries=(
            RenderQueueEntry(
                entry_id="Q-001",
                job_id="JOB-001",
                clip_id="CLIP-001",
                state=QueueState.COMPLETED,
                created_at=NOW - timedelta(minutes=30),
                updated_at=NOW - timedelta(minutes=20),
            ),
            RenderQueueEntry(
                entry_id="Q-002",
                job_id="JOB-002",
                clip_id="CLIP-002",
                state=QueueState.RUNNING,
                claimed_by="worker-a",
                created_at=NOW - timedelta(minutes=20),
                updated_at=NOW - timedelta(minutes=16),
            ),
        ),
    )


def _worker(worker_id: str = "worker-a") -> WorkerIdentity:
    return WorkerIdentity(
        worker_id=worker_id,
        executor_id="mock",
        capabilities=frozenset({RenderCapability.TEXT_TO_VIDEO}),
    )


def test_worker_health_and_active_lease_availability() -> None:
    lease = LeaseManager().acquire(
        "JOB-002",
        "worker-a",
        duration_seconds=120,
        now=NOW,
    )
    observations = (
        WorkerObservation(_worker(), NOW, lease),
        WorkerObservation(_worker("worker-b"), NOW - timedelta(seconds=90)),
        WorkerObservation(_worker("worker-c"), NOW - timedelta(seconds=240)),
    )

    snapshot = ProductionMonitor().snapshot(
        _pipeline(),
        _queue(),
        observations,
        now=NOW,
    )

    assert tuple(worker.health for worker in snapshot.workers) == (
        WorkerHealth.HEALTHY,
        WorkerHealth.STALE,
        WorkerHealth.OFFLINE,
    )
    assert snapshot.workers[0].available is False
    assert snapshot.workers[0].active_job_id == "JOB-002"


def test_queue_and_pipeline_progress_are_aggregated() -> None:
    snapshot = ProductionMonitor().snapshot(_pipeline(), _queue(), now=NOW)

    assert snapshot.queue.total == 2
    assert snapshot.queue.completed == 1
    assert snapshot.queue.running == 1
    assert snapshot.queue.completion_percentage == 50.0
    assert snapshot.pipeline.total == 2
    assert snapshot.pipeline.completed == 1
    assert snapshot.pipeline.running == 1
    assert snapshot.pipeline.completion_percentage == 50.0


def test_execution_metrics_include_duration_and_failure_codes() -> None:
    results = (
        ExecutionResult(
            job_id="JOB-001",
            worker_id="worker-a",
            succeeded=True,
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=10),
        ),
        ExecutionResult(
            job_id="JOB-002",
            worker_id="worker-b",
            succeeded=False,
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=30),
            error_code=ExecutorErrorCode.TIMEOUT,
            error_message="Timed out",
        ),
    )

    metrics = ProductionMonitor().snapshot(
        _pipeline(),
        _queue(),
        results=results,
        now=NOW,
    ).metrics

    assert metrics.total_results == 2
    assert metrics.succeeded == 1
    assert metrics.failed == 1
    assert metrics.success_percentage == 50.0
    assert metrics.average_duration_seconds == 20.0
    assert metrics.maximum_duration_seconds == 30.0
    assert metrics.failures_by_code == (("timeout", 1),)


def test_stalled_and_blocked_queue_entries_create_diagnostics() -> None:
    queue = _queue()
    blocked = replace(
        queue.entries[0],
        entry_id="Q-003",
        job_id="JOB-003",
        state=QueueState.BLOCKED,
    )
    queue = replace(queue, entries=(*queue.entries, blocked))

    snapshot = ProductionMonitor().snapshot(_pipeline(), queue, now=NOW)
    codes = {diagnostic.code for diagnostic in snapshot.diagnostics}

    assert "QUEUE_ENTRY_STALLED" in codes
    assert "QUEUE_ENTRY_BLOCKED" in codes


def test_worker_health_diagnostics_are_reported() -> None:
    observations = (
        WorkerObservation(_worker("worker-b"), NOW - timedelta(seconds=90)),
        WorkerObservation(_worker("worker-c"), NOW - timedelta(seconds=240)),
    )

    snapshot = ProductionMonitor().snapshot(
        _pipeline(),
        _queue(),
        observations,
        now=NOW,
    )
    codes = {diagnostic.code for diagnostic in snapshot.diagnostics}

    assert "WORKER_HEARTBEAT_STALE" in codes
    assert "WORKER_OFFLINE" in codes


def test_events_are_sorted_and_config_is_validated() -> None:
    events = (
        ProductionEvent("EV-002", "completed", NOW + timedelta(seconds=2), "done"),
        ProductionEvent("EV-001", "started", NOW, "started"),
    )

    snapshot = ProductionMonitor().snapshot(
        _pipeline(),
        _queue(),
        events=events,
        now=NOW,
    )

    assert tuple(event.event_id for event in snapshot.events) == ("EV-001", "EV-002")
    config = ProductionMonitoringConfig(
        stale_after_seconds=30,
        offline_after_seconds=90,
        stalled_after_seconds=300,
    )
    assert ProductionMonitor(config).config == config
