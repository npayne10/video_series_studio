"""Integration coverage for multi-shot prompt batch compilation."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationItem,
    BatchCompilationRequest,
    BatchCompilationStatus,
    BatchPromptCompilationService,
    PromptGraphBuildContext,
    PromptGraphResolver,
    PromptGraphSource,
    PromptNodeKind,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _sources(name: str) -> tuple[PromptGraphSource, ...]:
    return (
        PromptGraphSource(
            "intent",
            PromptNodeKind.VISUAL_INTENT,
            "Intent",
            f"{name} crosses the Xorix skyline.",
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


def _context(shot_id: str) -> PromptGraphBuildContext:
    return PromptGraphBuildContext(
        f"GRAPH-{shot_id}",
        "XORIX",
        "EP-001",
        "SCN-001",
        shot_id,
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PRODUCTION,
        workflow_id="ltx23_production_v1",
    )


def test_bootstrapped_service_compiles_multiple_shots(tmp_path: Path) -> None:
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
        resolver.register("SHT-001", _sources("Iron Horizon"))
        resolver.register("SHT-002", _sources("Guild shuttle"))
        request = BatchCompilationRequest.create(
            "BATCH-XORIX-001",
            (
                BatchCompilationItem("SHOT-2", _context("SHT-002"), sequence=2),
                BatchCompilationItem("SHOT-1", _context("SHT-001"), sequence=1),
            ),
        )

        job = application.services.require(BatchPromptCompilationService).compile(
            request
        )

        assert job.status is BatchCompilationStatus.COMPLETED
        assert tuple(result.shot_id for result in job.results) == (
            "SHT-001",
            "SHT-002",
        )
        assert "Iron Horizon" in job.packages[0].positive_prompt
        assert "Guild shuttle" in job.packages[1].positive_prompt
    finally:
        application.shutdown()
