"""Tests for aggregate batch compilation statistics."""

from vscs.application.prompt_graph import BatchCompilationHistory, BatchStatisticsService
from tests.unit.test_batch_compilation_history import _job
from vscs.application.prompt_graph import BatchCompilationStatus


def test_statistics_aggregate_history_records() -> None:
    history = BatchCompilationHistory()
    history.record(_job("BATCH-001", BatchCompilationStatus.COMPLETED))
    history.record(_job("BATCH-002", BatchCompilationStatus.FAILED))

    statistics = BatchStatisticsService(history).calculate()

    assert statistics.total_batches == 2
    assert statistics.total_items == 2
    assert statistics.completed_items == 1
    assert statistics.failed_items == 1
    assert statistics.failure_rate == 0.5
