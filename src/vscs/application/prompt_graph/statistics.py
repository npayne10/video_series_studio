"""Aggregate operational statistics for batch compilation history."""

from __future__ import annotations

from dataclasses import dataclass

from .history import BatchCompilationHistory


@dataclass(frozen=True, slots=True)
class BatchStatistics:
    """Aggregate metrics calculated from immutable batch history."""

    total_batches: int
    total_items: int
    completed_items: int
    skipped_items: int
    failed_items: int
    cancelled_items: int
    average_duration_seconds: float
    fastest_batch_id: str | None
    slowest_batch_id: str | None
    average_throughput_per_minute: float
    average_completion_percentage: float
    failure_rate: float
    skip_rate: float


@dataclass(slots=True)
class BatchStatisticsService:
    """Calculate production metrics from batch history."""

    history: BatchCompilationHistory

    def calculate(self) -> BatchStatistics:
        records = self.history.all()
        if not records:
            return BatchStatistics(
                total_batches=0,
                total_items=0,
                completed_items=0,
                skipped_items=0,
                failed_items=0,
                cancelled_items=0,
                average_duration_seconds=0.0,
                fastest_batch_id=None,
                slowest_batch_id=None,
                average_throughput_per_minute=0.0,
                average_completion_percentage=0.0,
                failure_rate=0.0,
                skip_rate=0.0,
            )
        total_items = sum(record.total_items for record in records)
        processed = sum(record.processed_items for record in records)
        durations = tuple(record.duration_seconds for record in records)
        completion_values = tuple(
            record.processed_items * 100.0 / record.total_items if record.total_items else 100.0
            for record in records
        )
        fastest = min(
            records,
            key=lambda record: (record.duration_seconds, record.batch_id),
        )
        slowest = max(
            records,
            key=lambda record: (record.duration_seconds, record.batch_id),
        )
        failed = sum(record.failed_items for record in records)
        skipped = sum(record.skipped_items for record in records)
        return BatchStatistics(
            total_batches=len(records),
            total_items=total_items,
            completed_items=sum(record.completed_items for record in records),
            skipped_items=skipped,
            failed_items=failed,
            cancelled_items=sum(record.cancelled_items for record in records),
            average_duration_seconds=sum(durations) / len(durations),
            fastest_batch_id=fastest.batch_id,
            slowest_batch_id=slowest.batch_id,
            average_throughput_per_minute=(
                sum(record.throughput_per_minute for record in records) / len(records)
            ),
            average_completion_percentage=sum(completion_values) / len(records),
            failure_rate=failed / processed if processed else 0.0,
            skip_rate=skipped / processed if processed else 0.0,
        )
