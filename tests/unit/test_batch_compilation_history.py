"""Tests for immutable batch compilation history."""

from datetime import UTC, datetime, timedelta

from vscs.application.prompt_graph import (
    BatchCompilationHistory,
    BatchCompilationItem,
    BatchCompilationItemResult,
    BatchCompilationItemStatus,
    BatchCompilationJob,
    BatchCompilationRequest,
    BatchCompilationStatus,
    PromptGraphBuildContext,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _job(batch_id: str, status: BatchCompilationStatus) -> BatchCompilationJob:
    context = PromptGraphBuildContext(
        graph_id=f"GRAPH-{batch_id}",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PREVIEW,
        workflow_id="ltx23_preview_v1",
    )
    request = BatchCompilationRequest.create(
        batch_id,
        (BatchCompilationItem("ITEM-001", context),),
    )
    started = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
    result_status = (
        BatchCompilationItemStatus.FAILED
        if status is BatchCompilationStatus.FAILED
        else BatchCompilationItemStatus.COMPLETED
    )
    result = BatchCompilationItemResult("ITEM-001", "SHT-001", result_status)
    return BatchCompilationJob(
        request,
        status,
        started,
        started + timedelta(seconds=30),
        (result,),
    )


def test_history_records_and_queries_terminal_batches() -> None:
    history = BatchCompilationHistory()
    completed = history.record(_job("BATCH-001", BatchCompilationStatus.COMPLETED))
    failed = history.record(_job("BATCH-002", BatchCompilationStatus.FAILED))

    assert history.latest() == failed
    assert history.by_batch("BATCH-001") == completed
    assert history.completed() == (completed,)
    assert history.failed() == (failed,)
    assert history.last(1) == (failed,)
    assert completed.duration_seconds == 30.0
    assert completed.renderer_ids == ("comfyui",)
