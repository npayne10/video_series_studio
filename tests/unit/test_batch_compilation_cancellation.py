"""Tests for safe cancellation between batch compilation items."""

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
    PromptGraphSource,
    PromptGraphValidator,
    PromptNodeKind,
    RendererPromptCompiler,
    RendererPromptProfileRegistry,
    default_renderer_prompt_profiles,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _context(shot_id: str) -> PromptGraphBuildContext:
    return PromptGraphBuildContext(
        graph_id=f"GRAPH-{shot_id}",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id=shot_id,
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PREVIEW,
        workflow_id="ltx23_preview_v1",
    )


def _sources() -> tuple[PromptGraphSource, ...]:
    return (
        PromptGraphSource(
            "intent",
            PromptNodeKind.VISUAL_INTENT,
            "Intent",
            "The Iron Horizon approaches Xorix.",
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
            "Stable Preview quality at 24 fps.",
            mandatory=True,
            sequence=5,
        ),
    )


def test_cancellation_preserves_completed_item_and_cancels_remaining() -> None:
    resolver = PromptGraphResolver()
    for shot_id in ("SHT-001", "SHT-002", "SHT-003"):
        resolver.register(shot_id, _sources())
    service = BatchPromptCompilationService(
        PromptGraphBuilder(resolver, PromptGraphDiagnosticsFactory()),
        PromptGraphCompiler(PromptGraphValidator()),
        RendererPromptProfileRegistry(default_renderer_prompt_profiles()),
        RendererPromptCompiler(),
    )
    request = BatchCompilationRequest.create(
        "BATCH-001",
        tuple(
            BatchCompilationItem(
                f"ITEM-{index}",
                _context(shot_id),
                sequence=index,
                require_production_ready=False,
            )
            for index, shot_id in enumerate(
                ("SHT-001", "SHT-002", "SHT-003"),
                start=1,
            )
        ),
    )
    cancel = False

    def on_progress(progress) -> None:
        nonlocal cancel
        if progress.completed_items == 1:
            cancel = True

    job = service.compile(
        request,
        on_progress=on_progress,
        should_cancel=lambda: cancel,
    )

    assert job.status is BatchCompilationStatus.CANCELLED
    assert len(job.completed_results) == 1
    assert len(job.cancelled_results) == 2
    assert all(
        result.status is BatchCompilationItemStatus.CANCELLED
        for result in job.cancelled_results
    )
    assert job.progress.percentage == 100
