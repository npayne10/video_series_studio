"""Tests for scheduler restoration from durable batch checkpoints."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationItem,
    BatchCompilationItemResult,
    BatchCompilationItemStatus,
    BatchCompilationJob,
    BatchCompilationRequest,
    BatchCompilationScheduler,
    BatchCompilationStatus,
    BatchQueueStatus,
    BatchRecoveryService,
    BatchRecoveryStore,
    PromptGraphBuildContext,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _request() -> BatchCompilationRequest:
    items = tuple(
        BatchCompilationItem(
            f"ITEM-{index}",
            PromptGraphBuildContext(
                graph_id=f"GRAPH-{index}",
                production_id="XORIX",
                container_id="EP-001",
                scene_id="SCN-001",
                shot_id=f"SHT-{index}",
                renderer=RendererKind.COMFYUI,
                quality_level=QualityLevel.PREVIEW,
                workflow_id="ltx23_preview_v1",
            ),
            sequence=index,
        )
        for index in (1, 2)
    )
    return BatchCompilationRequest.create("BATCH-RESTORE", items)


@dataclass
class _Compiler:
    calls: list[tuple[str, ...]]

    def compile(
        self,
        request,
        *,
        on_progress=None,
        on_result=None,
        should_cancel=None,
    ):
        self.calls.append(tuple(item.item_id for item in request.items))
        now = datetime.now(UTC)
        results = tuple(
            BatchCompilationItemResult(
                item.item_id,
                item.context.shot_id,
                BatchCompilationItemStatus.COMPLETED,
            )
            for item in request.items
        )
        if on_result is not None:
            for result in results:
                on_result(result)
        return BatchCompilationJob(
            request,
            BatchCompilationStatus.COMPLETED,
            now,
            now,
            results,
        )


def test_scheduler_restores_only_unfinished_items(tmp_path: Path) -> None:
    path = tmp_path / "recovery.json"
    original = BatchRecoveryService(BatchRecoveryStore(path))
    original.begin(_request())
    original.record_result(
        "BATCH-RESTORE",
        BatchCompilationItemResult(
            "ITEM-1",
            "SHT-1",
            BatchCompilationItemStatus.COMPLETED,
        ),
    )

    recovered = BatchRecoveryService(BatchRecoveryStore(path))
    compiler = _Compiler([])
    scheduler = BatchCompilationScheduler(
        compiler,  # type: ignore[arg-type]
        recovery_service=recovered,
    )

    restored = scheduler.restore_pending()
    completed = scheduler.run_next()

    assert len(restored) == 1
    assert tuple(item.item_id for item in restored[0].request.items) == ("ITEM-2",)
    assert completed is not None
    assert completed.status is BatchQueueStatus.COMPLETED
    assert compiler.calls == [("ITEM-2",)]
    assert recovered.pending_checkpoints() == ()
