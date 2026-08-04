"""Integration coverage for scheduler-driven incremental compilation."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationItem,
    BatchCompilationItemStatus,
    BatchCompilationRequest,
    BatchCompilationScheduler,
    CompilationDependency,
    CompilationDependencyKind,
    IncrementalCompilationHistory,
    PromptGraphBuildContext,
    PromptGraphResolver,
    PromptGraphSource,
    PromptNodeKind,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_scheduler_skips_unchanged_and_rebuilds_invalidated_dependency(
    tmp_path: Path,
) -> None:
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
        history = application.services.require(IncrementalCompilationHistory)
        resolver.register(
            "SHT-001",
            (
                PromptGraphSource(
                    "intent",
                    PromptNodeKind.VISUAL_INTENT,
                    "Intent",
                    "Iron Horizon approaches Xorix.",
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
            ),
        )
        context = PromptGraphBuildContext(
            "GRAPH-SHT-001",
            "XORIX",
            "EP-001",
            "SCN-001",
            "SHT-001",
            renderer=RendererKind.COMFYUI,
            quality_level=QualityLevel.PRODUCTION,
            workflow_id="ltx23_production_v1",
        )
        dependency = CompilationDependency(
            CompilationDependencyKind.CANONICAL_ASSET,
            "CAP-SHP-IRON-HORIZON",
            "cap-v1",
        )

        for batch_id in ("BATCH-001", "BATCH-002"):
            scheduler.enqueue(
                BatchCompilationRequest.create(
                    batch_id,
                    (
                        BatchCompilationItem(
                            "ITEM-001",
                            context,
                            dependencies=(dependency,),
                        ),
                    ),
                )
            )
        first, second = scheduler.run_all()

        assert first.job is not None
        assert second.job is not None
        assert first.job.results[0].status is BatchCompilationItemStatus.COMPLETED
        assert second.job.results[0].status is BatchCompilationItemStatus.SKIPPED

        affected = history.invalidate_dependency(
            CompilationDependencyKind.CANONICAL_ASSET,
            "CAP-SHP-IRON-HORIZON",
        )
        scheduler.enqueue(
            BatchCompilationRequest.create(
                "BATCH-003",
                (
                    BatchCompilationItem(
                        "ITEM-001",
                        context,
                        dependencies=(dependency,),
                    ),
                ),
            )
        )
        rebuilt = scheduler.run_next()

        assert affected == ("ITEM-001",)
        assert rebuilt is not None
        assert rebuilt.job is not None
        assert rebuilt.job.results[0].status is BatchCompilationItemStatus.COMPLETED
    finally:
        application.shutdown()
