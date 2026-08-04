"""Tests for checksum-based incremental prompt compilation."""

from __future__ import annotations

from vscs.application.prompt_graph import (
    BatchCompilationItem,
    BatchCompilationItemStatus,
    BatchCompilationRequest,
    BatchPromptCompilationService,
    CompilationDependency,
    CompilationDependencyKind,
    IncrementalCompilationHistory,
    IncrementalCompilationService,
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


def _context() -> PromptGraphBuildContext:
    return PromptGraphBuildContext(
        "GRAPH-SHT-001",
        "XORIX",
        "EP-001",
        "SCN-001",
        "SHT-001",
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PRODUCTION,
        workflow_id="ltx23_production_v1",
    )


def _sources(text: str = "Iron Horizon approaches Xorix.") -> tuple[PromptGraphSource, ...]:
    return (
        PromptGraphSource(
            "intent",
            PromptNodeKind.VISUAL_INTENT,
            "Intent",
            text,
            mandatory=True,
            sequence=1,
        ),
        PromptGraphSource(
            "camera",
            PromptNodeKind.CAMERA,
            "Camera",
            "Wide tracking shot.",
            mandatory=True,
            sequence=2,
        ),
        PromptGraphSource(
            "lighting",
            PromptNodeKind.LIGHTING,
            "Lighting",
            "Natural daylight.",
            mandatory=True,
            sequence=3,
        ),
        PromptGraphSource(
            "renderer",
            PromptNodeKind.RENDERER,
            "Renderer",
            "Renderer-neutral video intent.",
            mandatory=True,
            sequence=4,
        ),
        PromptGraphSource(
            "quality",
            PromptNodeKind.QUALITY,
            "Quality",
            "Production quality at 24 fps.",
            mandatory=True,
            sequence=5,
        ),
    )


def _service(
    resolver: PromptGraphResolver,
) -> tuple[BatchPromptCompilationService, IncrementalCompilationHistory]:
    history = IncrementalCompilationHistory()
    incremental = IncrementalCompilationService(history)
    return (
        BatchPromptCompilationService(
            PromptGraphBuilder(resolver, PromptGraphDiagnosticsFactory()),
            PromptGraphCompiler(PromptGraphValidator()),
            RendererPromptProfileRegistry(default_renderer_prompt_profiles()),
            RendererPromptCompiler(),
            incremental,
        ),
        history,
    )


def _item(*, checksum: str = "cap-v1", force: bool = False) -> BatchCompilationItem:
    return BatchCompilationItem(
        "ITEM-001",
        _context(),
        dependencies=(
            CompilationDependency(
                CompilationDependencyKind.CANONICAL_ASSET,
                "CAP-SHP-IRON-HORIZON",
                checksum,
            ),
        ),
        force_recompile=force,
    )


def test_unchanged_item_is_skipped_and_reuses_package() -> None:
    resolver = PromptGraphResolver()
    resolver.register("SHT-001", _sources())
    service, history = _service(resolver)

    first = service.compile(BatchCompilationRequest.create("BATCH-001", (_item(),)))
    second = service.compile(BatchCompilationRequest.create("BATCH-002", (_item(),)))

    assert first.results[0].status is BatchCompilationItemStatus.COMPLETED
    assert second.results[0].status is BatchCompilationItemStatus.SKIPPED
    assert second.packages[0] is first.packages[0]
    assert second.progress.skipped_items == 1
    assert len(history.all()) == 1


def test_graph_or_dependency_change_recompiles_item() -> None:
    resolver = PromptGraphResolver()
    resolver.register("SHT-001", _sources())
    service, _history = _service(resolver)
    service.compile(BatchCompilationRequest.create("BATCH-001", (_item(),)))

    resolver.register("SHT-001", _sources("Iron Horizon begins descent."))
    graph_changed = service.compile(
        BatchCompilationRequest.create("BATCH-002", (_item(),))
    )
    dependency_changed = service.compile(
        BatchCompilationRequest.create("BATCH-003", (_item(checksum="cap-v2"),))
    )

    assert graph_changed.results[0].status is BatchCompilationItemStatus.COMPLETED
    assert dependency_changed.results[0].status is BatchCompilationItemStatus.COMPLETED


def test_explicit_item_and_dependency_invalidation_force_recompile() -> None:
    resolver = PromptGraphResolver()
    resolver.register("SHT-001", _sources())
    service, history = _service(resolver)
    request = BatchCompilationRequest.create("BATCH-001", (_item(),))
    service.compile(request)

    assert history.invalidate_item("ITEM-001")
    item_invalidated = service.compile(
        BatchCompilationRequest.create("BATCH-002", (_item(),))
    )
    affected = history.invalidate_dependency(
        CompilationDependencyKind.CANONICAL_ASSET,
        "CAP-SHP-IRON-HORIZON",
    )
    dependency_invalidated = service.compile(
        BatchCompilationRequest.create("BATCH-003", (_item(),))
    )

    assert affected == ("ITEM-001",)
    assert item_invalidated.results[0].status is BatchCompilationItemStatus.COMPLETED
    assert dependency_invalidated.results[0].status is BatchCompilationItemStatus.COMPLETED


def test_force_recompile_bypasses_matching_fingerprint() -> None:
    resolver = PromptGraphResolver()
    resolver.register("SHT-001", _sources())
    service, _history = _service(resolver)
    service.compile(BatchCompilationRequest.create("BATCH-001", (_item(),)))

    forced = service.compile(
        BatchCompilationRequest.create("BATCH-002", (_item(force=True),))
    )

    assert forced.results[0].status is BatchCompilationItemStatus.COMPLETED
