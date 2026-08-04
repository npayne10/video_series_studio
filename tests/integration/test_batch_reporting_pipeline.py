"""Integration coverage for scheduler progress, history and reporting."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationHistory,
    BatchCompilationItem,
    BatchCompilationRequest,
    BatchCompilationScheduler,
    BatchProgressTracker,
    BatchReportingService,
    BatchStatisticsService,
    PromptGraphBuildContext,
    PromptGraphResolver,
    PromptGraphSource,
    PromptNodeKind,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_scheduler_records_progress_history_statistics_and_report(tmp_path: Path) -> None:
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
        resolver.register(
            "SHT-001",
            (
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
                    "Preview quality at 24 fps.",
                    mandatory=True,
                    sequence=5,
                ),
            ),
        )
        context = PromptGraphBuildContext(
            "GRAPH-001",
            "XORIX",
            "EP-001",
            "SCN-001",
            "SHT-001",
            renderer=RendererKind.COMFYUI,
            quality_level=QualityLevel.PREVIEW,
            workflow_id="ltx23_preview_v1",
        )
        request = BatchCompilationRequest.create(
            "BATCH-001",
            (
                BatchCompilationItem(
                    "ITEM-001",
                    context,
                    require_production_ready=False,
                ),
            ),
        )
        scheduler = application.services.require(BatchCompilationScheduler)
        scheduler.enqueue(request)

        entry = scheduler.run_next()

        assert entry is not None
        history = application.services.require(BatchCompilationHistory)
        tracker = application.services.require(BatchProgressTracker)
        statistics = application.services.require(BatchStatisticsService).calculate()
        report = application.services.require(BatchReportingService).for_batch("BATCH-001")
        assert history.latest() is not None
        assert tracker.latest("BATCH-001") is not None
        assert statistics.total_batches == 1
        assert report is not None
        assert "BATCH-001" in report.to_markdown()
    finally:
        application.shutdown()
