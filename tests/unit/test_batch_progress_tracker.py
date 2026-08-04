"""Tests for live batch compilation progress metrics."""

from datetime import UTC, datetime, timedelta

from vscs.application.prompt_graph import (
    BatchCompilationProgress,
    BatchCompilationStatus,
    BatchProgressTracker,
)


def test_progress_tracker_calculates_throughput_eta_and_success_rate() -> None:
    tracker = BatchProgressTracker()
    started = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
    tracker.update(
        BatchCompilationProgress(
            batch_id="BATCH-001",
            status=BatchCompilationStatus.RUNNING,
            total_items=10,
            completed_items=0,
            skipped_items=0,
            failed_items=0,
            cancelled_items=0,
            remaining_items=10,
        ),
        observed_at=started,
    )

    snapshot = tracker.update(
        BatchCompilationProgress(
            batch_id="BATCH-001",
            status=BatchCompilationStatus.RUNNING,
            total_items=10,
            completed_items=3,
            skipped_items=1,
            failed_items=1,
            cancelled_items=0,
            remaining_items=5,
            current_item_id="ITEM-005",
        ),
        observed_at=started + timedelta(minutes=1),
    )

    assert snapshot.metrics.items_per_minute == 5.0
    assert snapshot.metrics.estimated_remaining_seconds == 60.0
    assert snapshot.metrics.success_rate == 0.8
    assert tracker.latest("BATCH-001") == snapshot
    assert len(tracker.events("BATCH-001")) == 2
