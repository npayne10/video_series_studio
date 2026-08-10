"""Integration coverage for graph-to-optimised-prompt compilation."""

from pathlib import Path

from vscs.application.prompt_graph import (
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphCompiler,
    PromptGraphResolver,
    PromptGraphSource,
    PromptNodeKind,
    PromptOptimizationService,
    RendererPromptProfileRegistry,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_graph_compiles_to_optimized_renderer_prompt(tmp_path: Path) -> None:
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
                    "Natural reflected planetary light.",
                    mandatory=True,
                    sequence=3,
                ),
                PromptGraphSource(
                    "ship",
                    PromptNodeKind.SHIP,
                    "Iron Horizon",
                    "The 145 metre Guild survey spacecraft has four rear fusion "
                    "engines producing controlled blue-white engine trails.",
                    canonical_asset_id="CAP-SHP-IRON-HORIZON",
                    reference_ids=("REF-SHP-IRON-HORIZON",),
                    mandatory=True,
                    sequence=4,
                ),
                PromptGraphSource(
                    "continuity",
                    PromptNodeKind.CONTINUITY,
                    "Continuity",
                    "Preserve spacecraft orientation, hull markings and engine state.",
                    mandatory=True,
                    sequence=5,
                ),
                PromptGraphSource(
                    "duplicate",
                    PromptNodeKind.OTHER,
                    "Repeated detail",
                    "The 145 metre Guild survey spacecraft has four rear fusion "
                    "engines producing controlled blue-white engine trails.",
                    sequence=6,
                ),
                PromptGraphSource(
                    "renderer",
                    PromptNodeKind.RENDERER,
                    "Renderer",
                    "Renderer-neutral cinematic intent.",
                    mandatory=True,
                    sequence=7,
                ),
                PromptGraphSource(
                    "quality",
                    PromptNodeKind.QUALITY,
                    "Quality",
                    "Preview quality at 24 fps.",
                    mandatory=True,
                    sequence=8,
                ),
                PromptGraphSource(
                    "negative",
                    PromptNodeKind.NEGATIVE,
                    "Restrictions",
                    "No orange engine trails and no extra engines.",
                    sequence=9,
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
        graph = application.services.require(PromptGraphBuilder).build(context).graph
        package = application.services.require(PromptGraphCompiler).compile(
            graph,
            require_production_ready=False,
        )
        profile = application.services.require(RendererPromptProfileRegistry).resolve(
            RendererKind.COMFYUI, QualityLevel.PREVIEW
        )
        optimized = application.services.require(PromptOptimizationService).optimize(
            package,
            profile,
        )

        assert optimized.profiled.positive_prompt.count("blue-white engine trails") == 1
        assert "145 metre Guild survey spacecraft" in optimized.profiled.positive_prompt
        assert "four rear fusion engines" in optimized.profiled.positive_prompt
        assert "Preserve spacecraft orientation" in optimized.profiled.positive_prompt
        assert "orange engine trails" in optimized.profiled.negative_prompt
        assert optimized.report.duplicate_fragments_removed == 1
        assert optimized.source.provenance.graph_checksum == package.provenance.graph_checksum
    finally:
        application.shutdown()
