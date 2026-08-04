"""Unit coverage for deterministic prompt optimisation."""

from dataclasses import replace

from vscs.application.prompt_graph import (
    PromptFragment,
    PromptGraphCompleteness,
    PromptGraphValidationReport,
    PromptOptimizationService,
    PromptOptimizationSeverity,
    PromptPackage,
    PromptPackageProvenance,
    PromptSection,
    PromptSectionKind,
    RendererPromptCompiler,
    RendererPromptProfile,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _package() -> PromptPackage:
    provenance = PromptPackageProvenance(
        graph_id="GRAPH-001",
        graph_version="1.0",
        graph_checksum="checksum",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id=None,
    )
    validation = PromptGraphValidationReport(
        "GRAPH-001",
        PromptGraphCompleteness(100, 100, 100, True),
    )
    sections = (
        PromptSection(
            PromptSectionKind.VISUAL_INTENT,
            (
                PromptFragment(
                    "intent",
                    "Intent",
                    "  Iron Horizon   approaches Xorix.  ",
                    mandatory=True,
                ),
            ),
        ),
        PromptSection(
            PromptSectionKind.ENVIRONMENT,
            (
                PromptFragment(
                    "ship",
                    "Ship",
                    "Four rear fusion engines produce blue-white engine trails.",
                    mandatory=True,
                ),
                PromptFragment(
                    "duplicate",
                    "Duplicate",
                    "Four rear fusion engines produce blue-white engine trails.",
                ),
                PromptFragment(
                    "optional",
                    "Optional",
                    "Decorative background traffic remains subtle and distant.",
                ),
            ),
        ),
        PromptSection(
            PromptSectionKind.NEGATIVE,
            (
                PromptFragment(
                    "negative",
                    "Negative",
                    "No orange engine trails and no extra engines.",
                ),
            ),
        ),
    )
    return PromptPackage(
        package_id="PKG-001",
        sections=sections,
        positive_prompt="",
        negative_prompt="",
        canonical_asset_ids=("CAP-SHP-IRON-HORIZON",),
        reference_ids=("REF-SHP-IRON-HORIZON",),
        provenance=provenance,
        validation=validation,
    )


def _profile(limit: int | None = None) -> RendererPromptProfile:
    return RendererPromptProfile(
        profile_id="test_profile",
        display_name="Test Profile",
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PREVIEW,
        section_order=(
            PromptSectionKind.VISUAL_INTENT,
            PromptSectionKind.ENVIRONMENT,
            PromptSectionKind.NEGATIVE,
        ),
        maximum_positive_characters=limit,
        maximum_negative_characters=100,
    )


def test_optimization_normalizes_and_removes_exact_duplicates() -> None:
    optimized = PromptOptimizationService(RendererPromptCompiler()).optimize(
        _package(),
        _profile(),
    )

    assert "Iron Horizon approaches Xorix." in optimized.profiled.positive_prompt
    assert optimized.profiled.positive_prompt.count("blue-white engine trails") == 1
    assert "orange engine trails" in optimized.profiled.negative_prompt
    assert optimized.report.duplicate_fragments_removed == 1
    assert optimized.report.characters_saved > 0
    assert optimized.source.provenance.graph_checksum == "checksum"


def test_optional_fragment_is_omitted_before_protected_details() -> None:
    optimized = PromptOptimizationService(RendererPromptCompiler()).optimize(
        _package(),
        _profile(110),
    )

    assert optimized.report.optional_fragments_omitted == 1
    assert "Decorative background traffic" not in optimized.profiled.positive_prompt
    assert "blue-white engine trails" in optimized.profiled.positive_prompt
    assert "Iron Horizon approaches Xorix" in optimized.profiled.positive_prompt
    assert optimized.report.within_profile_limits


def test_protected_content_is_preserved_when_it_exceeds_profile_limit() -> None:
    package = replace(
        _package(),
        sections=tuple(
            section
            for section in _package().sections
            if section.kind is not PromptSectionKind.ENVIRONMENT
        ),
    )
    optimized = PromptOptimizationService(RendererPromptCompiler()).optimize(
        package,
        _profile(10),
    )

    assert "Iron Horizon approaches Xorix" in optimized.profiled.positive_prompt
    assert not optimized.report.within_profile_limits
    assert any(
        diagnostic.code == "optimization.protected_content_exceeds_limit"
        and diagnostic.severity is PromptOptimizationSeverity.WARNING
        for diagnostic in optimized.report.diagnostics
    )
