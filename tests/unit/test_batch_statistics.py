"""Tests for aggregate batch compilation statistics."""

from datetime import UTC, datetime, timedelta

from vscs.application.prompt_graph import (
    BatchCompilationHistory,
    BatchCompilationItem,
    BatchCompilationItemResult,
    BatchCompilationItemStatus,
    BatchCompilationJob,
    BatchCompilationRequest,
    BatchCompilationStatus,
    BatchStatisticsService,
    PromptGraphBuildContext,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _record(history: BatchCompilationHistory, batch_id: str, failed: bool) -> None:
    context = PromptGraphBuildContext(
        f"GRAPH-{batch_id}",
        "XORIX",
        "EP-001",
        "SCN-001",
        "SHT-001",
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PREVIEW,
        workflow_id="ltx23_preview_v1",
    )
    request = BatchCompilationRequest.create(
        batch_id,
        (BatchCompilationItem("ITEM-001", context),),
    )
    started = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
    item_status = (
        BatchCompilationItemStatus.FAILED if failed else BatchCompilationItemStatus.COMPLETED
    )
    job_status = BatchCompilationStatus.FAILED if failed else BatchCompilationStatus.COMPLETED
    history.record(
        BatchCompilationJob(
            request,
            job_status,
            started,
            started + timedelta(seconds=30),
            (BatchCompilationItemResult("ITEM-001", "SHT-001", item_status),),
        )
    )


def test_statistics_aggregate_history_records() -> None:
    history = BatchCompilationHistory()
    _record(history, "BATCH-001", False)
    _record(history, "BATCH-002", True)

    statistics = BatchStatisticsService(history).calculate()

    assert statistics.total_batches == 2
    assert statistics.total_items == 2
    assert statistics.completed_items == 1
    assert statistics.failed_items == 1
    assert statistics.failure_rate == 0.5
