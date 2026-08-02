"""Tests for the Phase 14.2 render queue engine."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from vscs.application.production_pipeline import (
    QueuePriority,
    QueueState,
    RenderQueue,
    RenderQueueEngine,
    RenderQueueEntry,
    RenderQueueError,
    RenderQueueSerializer,
    RenderQueueValidator,
)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _queue() -> RenderQueue:
    first = RenderQueueEntry(
        entry_id="Q-001",
        job_id="JOB-001",
        clip_id="CLIP-001",
        priority=QueuePriority.NORMAL,
        maximum_attempts=2,
        created_at=NOW,
        updated_at=NOW,
    )
    second = RenderQueueEntry(
        entry_id="Q-002",
        job_id="JOB-002",
        clip_id="CLIP-002",
        priority=QueuePriority.HIGH,
        dependencies=("Q-001",),
        created_at=NOW + timedelta(seconds=1),
        updated_at=NOW,
    )
    urgent = RenderQueueEntry(
        entry_id="Q-003",
        job_id="JOB-003",
        clip_id="CLIP-003",
        priority=QueuePriority.URGENT,
        created_at=NOW + timedelta(seconds=2),
        updated_at=NOW,
    )
    return RenderQueue(
        queue_id="QUEUE-001",
        pipeline_id="PIPELINE-001",
        entries=(first, second, urgent),
    )


def test_ready_entries_respect_dependencies_and_priority() -> None:
    ready = RenderQueueEngine().ready_entries(_queue(), NOW)

    assert tuple(entry.entry_id for entry in ready) == ("Q-003", "Q-001")


def test_completion_releases_dependent_entry() -> None:
    engine = RenderQueueEngine()
    queue = engine.claim(_queue(), "Q-001", "worker-a", NOW)
    queue = engine.start(queue, "Q-001", NOW)
    queue = engine.complete(queue, "Q-001", NOW + timedelta(seconds=10))

    assert queue.entry("Q-001").state is QueueState.COMPLETED
    assert queue.entry("Q-002").state is QueueState.READY


def test_failure_schedules_retry_then_terminal_failure() -> None:
    engine = RenderQueueEngine()
    queue = engine.claim(_queue(), "Q-001", "worker-a", NOW)
    queue = engine.start(queue, "Q-001", NOW)
    queue = engine.fail(
        queue,
        "Q-001",
        "provider timeout",
        retry_delay_seconds=30,
        now=NOW + timedelta(seconds=5),
    )

    entry = queue.entry("Q-001")
    assert entry.state is QueueState.RETRYING
    assert entry.attempt_count == 1
    assert entry.attempts[0].succeeded is False
    assert entry.attempts[0].error_message == "provider timeout"
    ready = engine.ready_entries(queue, NOW + timedelta(seconds=20))
    assert tuple(item.entry_id for item in ready) == ("Q-003",)

    queue = engine.refresh(queue, NOW + timedelta(seconds=40))
    queue = engine.claim(queue, "Q-001", "worker-b", NOW + timedelta(seconds=40))
    queue = engine.start(queue, "Q-001", NOW + timedelta(seconds=40))
    queue = engine.fail(
        queue,
        "Q-001",
        "second failure",
        now=NOW + timedelta(seconds=50),
    )

    assert queue.entry("Q-001").state is QueueState.FAILED
    assert queue.entry("Q-002").state is QueueState.BLOCKED


def test_cancelled_dependency_blocks_downstream_entry() -> None:
    queue = RenderQueueEngine().cancel(_queue(), "Q-001", NOW)

    assert queue.entry("Q-001").state is QueueState.CANCELLED
    assert queue.entry("Q-002").state is QueueState.BLOCKED


def test_invalid_transitions_are_rejected() -> None:
    engine = RenderQueueEngine()

    with pytest.raises(RenderQueueError):
        engine.start(_queue(), "Q-001", NOW)
    with pytest.raises(RenderQueueError):
        engine.claim(_queue(), "Q-002", "worker-a", NOW)
    with pytest.raises(RenderQueueError):
        engine.claim(_queue(), "Q-001", "", NOW)


def test_queue_validation_and_json_round_trip() -> None:
    queue = RenderQueueEngine().refresh(_queue(), NOW)
    validator = RenderQueueValidator()
    serializer = RenderQueueSerializer(validator)

    result = validator.validate(queue)
    restored = serializer.loads(serializer.dumps(queue))

    assert result.passed is True
    assert restored == queue
    assert serializer.checksum(restored) == serializer.checksum(queue)


def test_validator_rejects_unknown_dependency_and_cycle() -> None:
    queue = _queue()
    invalid = replace(
        queue,
        entries=(
            replace(queue.entries[0], dependencies=("Q-002",)),
            replace(queue.entries[1], dependencies=("Q-001", "MISSING")),
            queue.entries[2],
        ),
    )

    result = RenderQueueValidator().validate(invalid)
    codes = {issue.code for issue in result.issues}

    assert result.passed is False
    assert "UNKNOWN_DEPENDENCY" in codes
    assert "DEPENDENCY_CYCLE" in codes
