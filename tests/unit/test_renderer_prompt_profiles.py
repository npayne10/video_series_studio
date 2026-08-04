"""Tests for renderer-specific prompt profiles."""

from vscs.application.prompt_graph import (
    PromptFragment,
    PromptGraphCompleteness,
    PromptGraphValidationReport,
    PromptPackage,
    PromptPackageProvenance,
    PromptSection,
    PromptSectionKind,
    RendererPromptCompiler,
    RendererPromptProfile,
    RendererPromptProfileRegistry,
    default_renderer_prompt_profiles,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _package() -> PromptPackage:
    validation = PromptGraphValidationReport(
        "GRAPH-001",
        PromptGraphCompleteness(100, 100, 100, True),
    )
    return PromptPackage(
        package_id="GRAPH-001:prompt",
        sections=(
            PromptSection(
                PromptSectionKind.VISUAL_INTENT,
                (PromptFragment("intent", "Intent", "A spacecraft approaches Xorix."),),
            ),
            PromptSection(
                PromptSectionKind.ENVIRONMENT,
                (
                    PromptFragment(
                        "ship",
                        "Iron Horizon",
                        "A 145 metre survey spacecraft with blue-white engine trails.",
                        canonical_asset_id="CAP-SHP-IRON-HORIZON",
                        reference_ids=("REF-SHP-IRON-HORIZON-01",),
                    ),
                ),
            ),
            PromptSection(
                PromptSectionKind.NEGATIVE,
                (PromptFragment("negative", "Negative", "No fantasy glow."),),
            ),
        ),
        positive_prompt="A spacecraft approaches Xorix.; A 145 metre survey spacecraft.",
        negative_prompt="No fantasy glow.",
        canonical_asset_ids=("CAP-SHP-IRON-HORIZON",),
        reference_ids=("REF-SHP-IRON-HORIZON-01",),
        provenance=PromptPackageProvenance(
            "GRAPH-001",
            "1.0",
            "a" * 64,
            "XORIX",
            "EP-001",
            "SCN-001",
            "SHT-001",
            None,
        ),
        validation=validation,
    )


def test_default_registry_resolves_preview_and_production() -> None:
    registry = RendererPromptProfileRegistry(default_renderer_prompt_profiles())

    preview = registry.resolve(RendererKind.COMFYUI, QualityLevel.PREVIEW)
    production = registry.resolve(RendererKind.COMFYUI, QualityLevel.PRODUCTION)

    assert preview.profile_id == "comfyui_preview_v1"
    assert production.profile_id == "comfyui_production_v1"
    assert not preview.include_section_labels
    assert production.include_section_labels


def test_renderer_compiler_preserves_positive_negative_separation() -> None:
    profile = RendererPromptProfileRegistry(
        default_renderer_prompt_profiles()
    ).resolve(RendererKind.COMFYUI, QualityLevel.PRODUCTION)

    compiled = RendererPromptCompiler().compile(_package(), profile)

    assert "Visual Intent:" in compiled.positive_prompt
    assert "blue-white engine trails" in compiled.positive_prompt
    assert "No fantasy glow" not in compiled.positive_prompt
    assert "Negative:" in compiled.negative_prompt
    assert "No fantasy glow" in compiled.negative_prompt


def test_profile_character_limit_is_reported_without_mutating_source() -> None:
    profile = RendererPromptProfile(
        profile_id="limited",
        display_name="Limited",
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PREVIEW,
        section_order=(PromptSectionKind.VISUAL_INTENT,),
        maximum_positive_characters=20,
    )
    source = _package()

    compiled = RendererPromptCompiler().compile(source, profile)

    assert compiled.positive_truncated
    assert len(compiled.positive_prompt) <= 20
    assert source.positive_prompt.startswith("A spacecraft approaches")
