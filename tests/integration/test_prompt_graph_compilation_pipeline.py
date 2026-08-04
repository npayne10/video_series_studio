"""Integration coverage for build, validate and compile prompt graph flow."""

from vscs.application.prompt_graph import (
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphCompiler,
    PromptGraphDiagnosticsFactory,
    PromptGraphResolver,
    PromptGraphResourceInventory,
    PromptGraphSource,
    PromptGraphValidator,
    PromptNodeKind,
    PromptSectionKind,
)
from vscs.application.rendering import QualityLevel, RendererKind


def test_builder_validator_compiler_pipeline_preserves_full_production_detail() -> None:
    resolver = PromptGraphResolver()
    resolver.register(
        "SHT-001",
        (
            PromptGraphSource(
                "intent",
                PromptNodeKind.VISUAL_INTENT,
                "Visual intent",
                "The Iron Horizon descends toward the Xorix starport.",
                mandatory=True,
                sequence=1,
            ),
            PromptGraphSource(
                "ship",
                PromptNodeKind.SHIP,
                "Iron Horizon",
                "The 145 metre Guild survey spacecraft retains four rear fusion "
                "engines with controlled blue-white engine trails.",
                canonical_asset_id="CAP-SHP-IRON-HORIZON",
                reference_ids=("REF-SHP-IRON-HORIZON-01",),
                mandatory=True,
                sequence=2,
            ),
            PromptGraphSource(
                "camera",
                PromptNodeKind.CAMERA,
                "Camera",
                "Wide tracking shot following the spacecraft through descent.",
                mandatory=True,
                sequence=3,
            ),
            PromptGraphSource(
                "lighting",
                PromptNodeKind.LIGHTING,
                "Lighting",
                "Natural Xorix daylight with restrained atmospheric scattering.",
                mandatory=True,
                sequence=4,
            ),
            PromptGraphSource(
                "continuity",
                PromptNodeKind.CONTINUITY,
                "Continuity",
                "Maintain hull markings, orientation and engine state.",
                mandatory=True,
                sequence=5,
            ),
            PromptGraphSource(
                "renderer",
                PromptNodeKind.RENDERER,
                "Renderer",
                "Renderer-neutral cinematic video intent.",
                mandatory=True,
                sequence=6,
            ),
            PromptGraphSource(
                "quality",
                PromptNodeKind.QUALITY,
                "Quality",
                "Production quality, 24 fps, consistent temporal detail.",
                mandatory=True,
                sequence=7,
            ),
            PromptGraphSource(
                "negative",
                PromptNodeKind.NEGATIVE,
                "Negative",
                "No side engines, fantasy glow or inconsistent hull geometry.",
                sequence=8,
            ),
        ),
    )
    builder = PromptGraphBuilder(resolver, PromptGraphDiagnosticsFactory())
    build = builder.build(
        PromptGraphBuildContext(
            graph_id="GRAPH-001",
            production_id="XORIX",
            container_id="EP-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
            renderer=RendererKind.COMFYUI,
            quality_level=QualityLevel.PRODUCTION,
            workflow_id="ltx23_production_v1",
        )
    )
    inventory = PromptGraphResourceInventory(
        canonical_asset_ids=frozenset({"CAP-SHP-IRON-HORIZON"}),
        reference_ids=frozenset({"REF-SHP-IRON-HORIZON-01"}),
    )

    package = PromptGraphCompiler(PromptGraphValidator()).compile(
        build.graph,
        inventory,
    )

    assert build.report.passed
    assert package.validation.completeness.production_ready
    assert "145 metre Guild survey spacecraft" in package.positive_prompt
    assert "controlled blue-white engine trails" in package.positive_prompt
    assert "No side engines" in package.negative_prompt
    assert package.section(PromptSectionKind.CONTINUITY) is not None
    assert package.provenance.graph_checksum
