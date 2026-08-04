"""Integration coverage for queued sequential batch compilation."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationItem,
    BatchCompilationRequest,
    BatchCompilationScheduler,
    BatchQueueStatus,
    PromptGraphBuildContext,
    PromptGraphResolver,
    PromptGraphSource,
    PromptNodeKind,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


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


def _sources(shot_id: str) -> tuple[PromptGraphSource, ...]:
    return (
        PromptGraphSource(
            "intent",
            PromptNodeKind.VISUAL_INTENT,
            "Intent",
            f"Shot {shot_id} establishes the Xorix approach.",
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


def test_bootstrapped_scheduler_executes_batches_in_fifo_order(tmp_path: Path) -> None:
    application = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.toml",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        resolver = application.services.require(PromptGraphResolver)
        scheduler = application.services.require(BatchCompilationScheduler)
        for shot_id in ("SHT-001", "SHT-002"):
            resolver.register(shot_id, _sources(shot_id))
        for batch_id, shot_id in (
            ("BATCH-002", "SHT-002"),
            ("BATCH-001", "SHT-001"),
        ):
            scheduler.enqueue(
                BatchCompilationRequest.create(
                    batch_id,
                    (
                        BatchCompilationItem(
                            f"ITEM-{shot_id}",
                            _context(shot_id),
                            require_production_ready=False,
                        ),
                    ),
                )
            )

        completed = scheduler.run_all()

        assert tuple(entry.batch_id for entry in completed) == (
            "BATCH-002",
            "BATCH-001",
        )
        assert all(entry.status is BatchQueueStatus.COMPLETED for entry in completed)
        assert all(entry.job is not None for entry in completed)
        assert len(scheduler.snapshot().terminal) == 2
    finally:
        application.shutdown()
