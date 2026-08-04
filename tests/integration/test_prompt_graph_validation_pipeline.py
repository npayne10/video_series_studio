"""Integration tests for prompt graph build and validation."""

from vscs.application.prompt_graph import (
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphDiagnosticsFactory,
    PromptGraphResolver,
    PromptGraphResourceInventory,
    PromptGraphSource,
    PromptGraphValidator,
    PromptNodeKind,
)
from vscs.application.rendering import QualityLevel, RendererKind


def test_builder_output_passes_production_readiness_validation() -> None:
    resolver = PromptGraphResolver()
    resolver.register(
        "SHT-001",
        (
            PromptGraphSource(
                "intent",
                PromptNodeKind.VISUAL_INTENT,
                "Visual intent",
                "Iron Horizon enters Xorix orbit under controlled thrust.",
                mandatory=True,
                sequence=1,
            ),
            PromptGraphSource(
                "ship",
                PromptNodeKind.SHIP,
                "Iron Horizon",
                "145-metre Guild survey vessel with four rear fusion engines.",
                canonical_asset_id="SHP-IRON-HORIZON",
                reference_ids=("REF-IRON-HORIZON",),
                mandatory=True,
                sequence=2,
            ),
            PromptGraphSource(
                "camera",
                PromptNodeKind.CAMERA,
                "Camera",
                "Wide orbital tracking shot.",
                sequence=3,
            ),
            PromptGraphSource(
                "lighting",
                PromptNodeKind.LIGHTING,
                "Lighting",
                "Natural sunlight from frame left.",
                sequence=4,
            ),
            PromptGraphSource(
                "continuity",
                PromptNodeKind.CONTINUITY,
                "Continuity",
                "Match the approved previous end frame.",
                sequence=5,
            ),
            PromptGraphSource(
                "renderer",
                PromptNodeKind.RENDERER,
                "Renderer",
                "ComfyUI with LTX 2.3.",
                sequence=6,
            ),
            PromptGraphSource(
                "quality",
                PromptNodeKind.QUALITY,
                "Quality",
                "Production quality profile.",
                sequence=7,
            ),
        ),
    )
    context = PromptGraphBuildContext(
        graph_id="GRAPH-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PRODUCTION,
        workflow_id="ltx23_production_v1",
    )

    build = PromptGraphBuilder(
        resolver,
        PromptGraphDiagnosticsFactory(),
    ).build(context)
    validation = PromptGraphValidator().validate(
        build.graph,
        PromptGraphResourceInventory(
            canonical_asset_ids=frozenset({"SHP-IRON-HORIZON"}),
            reference_ids=frozenset({"REF-IRON-HORIZON"}),
        ),
    )

    assert build.report.passed
    assert validation.passed
    assert validation.completeness.percentage == 100
    assert validation.completeness.production_ready
