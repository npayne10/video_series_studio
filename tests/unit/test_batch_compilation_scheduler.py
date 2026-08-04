"""Tests for FIFO batch queue and sequential scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from vscs.application.prompt_graph import (
    BatchCompilationItem,
    BatchCompilationItemResult,
    BatchCompilationItemStatus,
    BatchCompilationJob,
    BatchCompilationProgress,
    BatchCompilationRequest,
    BatchCompilationScheduler,
    BatchCompilationStatus,
    BatchQueueStatus,
    PromptGraphBuildContext,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _request(batch_id: str, shot_id: str) -> BatchCompilationRequest:
    context = PromptGraphBuildContext(
        graph_id=f"GRAPH-{shot_id}",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id=shot_id,
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PREVIEW,
        workflow_id="ltx23_preview_v1",
    )
    return BatchCompilationRequest.create(
        batch_id,
        (BatchCompilationItem(f"ITEM-{shot_id}", context),),
    )


@dataclass
class _FakeCompiler:
    calls: list[str]

    def compile(self, request, *, on_progress=None, should_cancel=None):
        self.calls.append(request.batch_id)
        now = datetime.now(UTC)
        if should_cancel is not None and should_cancel():
            result = BatchCompilationItemResult(
                request.items[0].item_id,
                request.items[0].context.shot_id,
                BatchCompilationItemStatus.CANCELLED,
            )
            status = BatchCompilationStatus.CANCELLED
        else:
            result = BatchCompilationItemResult(
                request.items[0].item_id,
                request.items[0].context.shot_id,
                BatchCompilationItemStatus.COMPLETED,
            )
            status = BatchCompilationStatus.COMPLETED
        progress = BatchCompilationProgress(
            request.batch_id,
            status,
            1,
            int(status is BatchCompilationStatus.COMPLETED),
            0,
            int(status is BatchCompilationStatus.CANCELLED),
            0,
        )
        if on_progress is not None:
            on_progress(progress)
        return BatchCompilationJob(request, status, now, now, (result,))


def test_scheduler_runs_batches_in_fifo_order() -> None:
    compiler = _FakeCompiler([])
    scheduler = BatchCompilationScheduler(compiler)  # type: ignore[arg-type]
    scheduler.enqueue(_request("BATCH-002", "SHT-002"))
    scheduler.enqueue(_request("BATCH-001", "SHT-001"))

    completed = scheduler.run_all()

    assert compiler.calls == ["BATCH-002", "BATCH-001"]
    assert tuple(entry.status for entry in completed) == (
        BatchQueueStatus.COMPLETED,
        BatchQueueStatus.COMPLETED,
    )
    assert scheduler.snapshot().pending == ()
    assert len(scheduler.snapshot().terminal) == 2


def test_pending_batch_can_be_cancelled_without_execution() -> None:
    compiler = _FakeCompiler([])
    scheduler = BatchCompilationScheduler(compiler)  # type: ignore[arg-type]
    scheduler.enqueue(_request("BATCH-001", "SHT-001"))

    cancelled = scheduler.cancel("BATCH-001")

    assert cancelled.status is BatchQueueStatus.CANCELLED
    assert cancelled.finished_at is not None
    assert scheduler.run_next() is None
    assert compiler.calls == []


def test_scheduler_rejects_duplicate_batch_ids() -> None:
    scheduler = BatchCompilationScheduler(_FakeCompiler([]))  # type: ignore[arg-type]
    request = _request("BATCH-001", "SHT-001")
    scheduler.enqueue(request)

    with pytest.raises(ValueError, match="already scheduled"):
        scheduler.enqueue(request)


def test_queue_snapshot_is_immutable_view() -> None:
    scheduler = BatchCompilationScheduler(_FakeCompiler([]))  # type: ignore[arg-type]
    first = scheduler.enqueue(_request("BATCH-001", "SHT-001"))
    snapshot = scheduler.snapshot()
    scheduler.enqueue(_request("BATCH-002", "SHT-002"))

    assert snapshot.entries == (first,)
    assert len(scheduler.snapshot().entries) == 2
