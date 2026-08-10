"""Integration coverage for graph compilation, profiling and prompt preview."""

from pathlib import Path

from vscs.application.prompt_graph import (
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphCompiler,
    PromptGraphResolver,
    PromptGraphResourceInventory,
    PromptGraphSource,
    PromptNodeKind,
    PromptPreviewService,
    PromptSectionKind,
    RendererPromptCompiler,
    RendererPromptProfileRegistry,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_graph_compiles_through_renderer_profile_into_preview(tmp_path: Path) -> None:
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
                    "Visual intent",
                    "The Iron Horizon approaches Xorix orbit.",
                    mandatory=True,
                    sequence=1,
                ),
                PromptGraphSource(
                    "ship",
                    PromptNodeKind.SHIP,
                    "Iron Horizon",
                    "The 145 metre survey spacecraft has four rear fusion engines "
                    "with controlled blue-white engine trails.",
                    canonical_asset_id="CAP-SHP-IRON-HORIZON",
                    reference_ids=("REF-SHP-IRON-HORIZON-01",),
                    mandatory=True,
                    sequence=2,
                ),
                PromptGraphSource(
                    "camera",
                    PromptNodeKind.CAMERA,
                    "Camera",
                    "Restrained wide orbital tracking shot.",
                    mandatory=True,
                    sequence=3,
                ),
                PromptGraphSource(
                    "lighting",
                    PromptNodeKind.LIGHTING,
                    "Lighting",
                    "Natural sunlight with realistic planetary bounce.",
                    mandatory=True,
                    sequence=4,
                ),
                PromptGraphSource(
                    "continuity",
                    PromptNodeKind.CONTINUITY,
                    "Continuity",
                    "Maintain hull orientation and engine state.",
                    mandatory=True,
                    sequence=5,
                ),
                PromptGraphSource(
                    "renderer",
                    PromptNodeKind.RENDERER,
                    "Renderer",
                    "ComfyUI cinematic video workflow.",
                    mandatory=True,
                    sequence=6,
                ),
                PromptGraphSource(
                    "quality",
                    PromptNodeKind.QUALITY,
                    "Quality",
                    "Production quality at 24 fps.",
                    mandatory=True,
                    sequence=7,
                ),
                PromptGraphSource(
                    "negative",
                    PromptNodeKind.NEGATIVE,
                    "Negative",
                    "No side engines or fantasy glow.",
                    sequence=8,
                ),
            ),
        )
        graph = (
            application.services.require(PromptGraphBuilder)
            .build(
                PromptGraphBuildContext(
                    "GRAPH-001",
                    "XORIX",
                    "EP-001",
                    "SCN-001",
                    "SHT-001",
                    renderer=RendererKind.COMFYUI,
                    quality_level=QualityLevel.PRODUCTION,
                    workflow_id="ltx23_production_v1",
                )
            )
            .graph
        )
        package = application.services.require(PromptGraphCompiler).compile(
            graph,
            PromptGraphResourceInventory(
                canonical_asset_ids=frozenset({"CAP-SHP-IRON-HORIZON"}),
                reference_ids=frozenset({"REF-SHP-IRON-HORIZON-01"}),
            ),
        )
        profile = application.services.require(RendererPromptProfileRegistry).resolve(
            RendererKind.COMFYUI, QualityLevel.PRODUCTION
        )
        profiled = application.services.require(RendererPromptCompiler).compile(
            package,
            profile,
        )
        preview = application.services.require(PromptPreviewService).create(profiled)

        assert "controlled blue-white engine trails" in preview.positive_prompt
        assert "No side engines" in preview.negative_prompt
        assert preview.section(PromptSectionKind.CONTINUITY) is not None
        assert preview.profile_id == "comfyui_production_v1"
        assert preview.canonical_asset_count == 1
        assert preview.reference_count == 1
    finally:
        application.shutdown()
