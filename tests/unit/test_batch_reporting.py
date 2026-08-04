"""Tests for deterministic batch compilation reports."""

from datetime import UTC, datetime, timedelta

from vscs.application.prompt_graph import (
    BatchCompilationHistory,
    BatchCompilationItem,
    BatchCompilationItemResult,
    BatchCompilationItemStatus,
    BatchCompilationJob,
    BatchCompilationRequest,
    BatchCompilationStatus,
    BatchReportingService,
    BatchStatisticsService,
    PromptGraphBuildContext,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _failed_job() -> BatchCompilationJob:
    context = PromptGraphBuildContext(
        "GRAPH-001",
        "XORIX",
        "EP-001",
        "SCN-001",
        "SHT-001",
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PRODUCTION,
        workflow_id="ltx23_production_v1",
    )
    request = BatchCompilationRequest.create(
        "BATCH-001",
        (BatchCompilationItem("ITEM-001", context),),
    )
    started = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
    result = BatchCompilationItemResult(
        "ITEM-001",
        "SHT-001",
        BatchCompilationItemStatus.FAILED,
        error_type="PromptGraphCompilationError",
        error_message="canonical reference missing",
    )
    return BatchCompilationJob(
        request,
        BatchCompilationStatus.FAILED,
        started,
        started + timedelta(seconds=15),
        (result,),
    )


def test_reporting_generates_deterministic_text_and_markdown() -> None:
    history = BatchCompilationHistory()
    service = BatchReportingService(history, BatchStatisticsService(history))

    report = service.record(_failed_job())

    assert "Batch Compilation Report: BATCH-001" in report.to_text()
    assert "PromptGraphCompilationError" in report.to_text()
    assert "# Batch Compilation Report — BATCH-001" in report.to_markdown()
    assert "canonical reference missing" in report.to_markdown()
    assert history.latest() == report.record
