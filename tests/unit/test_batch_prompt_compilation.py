"""Tests for deterministic batch prompt compilation orchestration."""

from __future__ import annotations

from vscs.application.prompt_graph import (
    BatchCompilationItem,
    BatchCompilationItemStatus,
    BatchCompilationRequest,
    BatchCompilationStatus,
    BatchPromptCompilationService,
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphCompiler,
    PromptGraphDiagnosticsFactory,
    PromptGraphResolver,
    PromptGraphResourceInventory,
    PromptGraphSource,
    PromptGraphValidator,
    PromptNodeKind,
    RendererPromptCompiler,
    RendererPromptProfileRegistry,
    default_renderer_prompt_profiles,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _service(resolver: PromptGraphResolver) -> BatchPromptCompilationService:
    return BatchPromptCompilationService(
        PromptGraphBuilder(resolver, PromptGraphDiagnosticsFactory()),
        PromptGraphCompiler(PromptGraphValidator()),
        RendererPromptProfileRegistry(default_renderer_prompt_profiles()),
        RendererPromptCompiler(),
    )


def _context(shot_id: str, quality: QualityLevel = QualityLevel.PRODUCTION) -> PromptGraphBuildContext:
    return PromptGraphBuildContext(
        graph_id=f"GRAPH-{shot_id}",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id=shot_id,
        renderer=RendererKind.COMFYUI,
        quality_level=quality,
        workflow_id=(
            "ltx23_preview_v1"
            if quality is QualityLevel.PREVIEW
            else "ltx23_production_v1"
        ),
    )


def _sources(label: str) -> tuple[PromptGraphSource, ...]:
    return (
        PromptGraphSource(
            "intent",
            PromptNodeKind.VISUAL_INTENT,
            "Intent",
            f"{label} approaches Xorix.",
            mandatory=True,
            sequence=1,
        ),
        PromptGraphSource(
            "camera",
            PromptNodeKind.CAMERA,
            "Camera",
            "Wide restrained tracking shot.",
            mandatory=True,
            sequence=2,
        ),
        PromptGraphSource(
            "lighting",
            PromptNodeKind.LIGHTING,
            "Lighting",
            "Natural planetary light.",
            mandatory=True,
            sequence=3,
        ),
        PromptGraphSource(
            "renderer",
            PromptNodeKind.RENDERER,
            "Renderer",
            "Renderer-neutral cinematic intent.",
            mandatory=True,
            sequence=4,
        ),
        PromptGraphSource(
            "quality",
            PromptNodeKind.QUALITY,
            "Quality",
            "Stable temporal quality at 24 fps.",
            mandatory=True,
            sequence=5,
        ),
        PromptGraphSource(
            "negative",
            PromptNodeKind.NEGATIVE,
            "Negative",
            "No visual clutter.",
            sequence=6,
        ),
    )


def test_batch_compiles_in_deterministic_sequence_and_reports_progress() -> None:
    resolver = PromptGraphResolver()
    resolver.register("SHT-001", _sources("Iron Horizon"))
    resolver.register("SHT-002", _sources("Personnel shuttle"))
    request = BatchCompilationRequest.create(
        "BATCH-001",
        (
            BatchCompilationItem("ITEM-002", _context("SHT-002"), sequence=2),
            BatchCompilationItem("ITEM-001", _context("SHT-001"), sequence=1),
        ),
    )
    progress = []

    job = _service(resolver).compile(request, on_progress=progress.append)

    assert job.status is BatchCompilationStatus.COMPLETED
    assert tuple(result.item_id for result in job.results) == ("ITEM-001", "ITEM-002")
    assert all(
        result.status is BatchCompilationItemStatus.COMPLETED
        for result in job.results
    )
    assert len(job.packages) == 2
    assert progress[0].status is BatchCompilationStatus.RUNNING
    assert progress[-1].status is BatchCompilationStatus.COMPLETED
    assert progress[-1].percentage == 100


def test_batch_isolates_one_failed_item_and_continues() -> None:
    resolver = PromptGraphResolver()
    resolver.register("SHT-001", _sources("Iron Horizon"))
    request = BatchCompilationRequest.create(
        "BATCH-002",
        (
            BatchCompilationItem("GOOD", _context("SHT-001"), sequence=1),
            BatchCompilationItem("BROKEN", _context("SHT-999"), sequence=2),
        ),
    )

    job = _service(resolver).compile(request)

    assert job.status is BatchCompilationStatus.COMPLETED_WITH_FAILURES
    assert len(job.completed_results) == 1
    assert len(job.failed_results) == 1
    assert job.failed_results[0].item_id == "BROKEN"
    assert job.failed_results[0].error_type == "PromptGraphCompilationError"


def test_batch_reports_failed_when_no_item_compiles() -> None:
    request = BatchCompilationRequest.create(
        "BATCH-003",
        (BatchCompilationItem("BROKEN", _context("SHT-999")),),
    )

    job = _service(PromptGraphResolver()).compile(request)

    assert job.status is BatchCompilationStatus.FAILED
    assert job.progress.failed_items == 1
    assert job.progress.remaining_items == 0


def test_batch_can_use_preview_profile_and_nonproduction_override() -> None:
    resolver = PromptGraphResolver()
    resolver.register("SHT-001", _sources("Iron Horizon"))
    item = BatchCompilationItem(
        "PREVIEW",
        _context("SHT-001", QualityLevel.PREVIEW),
        inventory=PromptGraphResourceInventory(),
        renderer_profile_id="comfyui_preview_v1",
        require_production_ready=False,
    )

    job = _service(resolver).compile(BatchCompilationRequest.create("BATCH-004", (item,)))

    assert job.status is BatchCompilationStatus.COMPLETED
    assert job.packages[0].profile.profile_id == "comfyui_preview_v1"


def test_request_rejects_duplicate_item_ids() -> None:
    item = BatchCompilationItem("DUPLICATE", _context("SHT-001"))

    try:
        BatchCompilationRequest.create("BATCH-005", (item, item))
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate batch item IDs were accepted")
