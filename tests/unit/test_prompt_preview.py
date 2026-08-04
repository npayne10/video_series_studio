"""Tests for structured prompt previews."""

from vscs.application.prompt_graph import (
    PromptFragment,
    PromptGraphCompleteness,
    PromptGraphValidationReport,
    PromptPackage,
    PromptPackageProvenance,
    PromptPreviewService,
    PromptSection,
    PromptSectionKind,
    ProfiledPromptPackage,
    RendererPromptProfileRegistry,
    default_renderer_prompt_profiles,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _profiled(*, truncated: bool = False) -> ProfiledPromptPackage:
    package = PromptPackage(
        package_id="GRAPH-001:prompt",
        sections=(
            PromptSection(
                PromptSectionKind.ENVIRONMENT,
                (
                    PromptFragment(
                        "ship",
                        "Iron Horizon",
                        "The Iron Horizon maintains blue-white engine trails.",
                        canonical_asset_id="CAP-SHP-IRON-HORIZON",
                        reference_ids=("REF-SHP-IRON-HORIZON-01",),
                    ),
                ),
            ),
        ),
        positive_prompt="The Iron Horizon maintains blue-white engine trails.",
        negative_prompt="",
        canonical_asset_ids=("CAP-SHP-IRON-HORIZON",),
        reference_ids=("REF-SHP-IRON-HORIZON-01",),
        provenance=PromptPackageProvenance(
            "GRAPH-001",
            "1.0",
            "b" * 64,
            "XORIX",
            "EP-001",
            "SCN-001",
            "SHT-001",
            None,
        ),
        validation=PromptGraphValidationReport(
            "GRAPH-001",
            PromptGraphCompleteness(100, 100, 100, True),
        ),
    )
    profile = RendererPromptProfileRegistry(
        default_renderer_prompt_profiles()
    ).resolve(RendererKind.COMFYUI, QualityLevel.PREVIEW)
    return ProfiledPromptPackage(
        package,
        profile,
        package.positive_prompt,
        package.negative_prompt,
        positive_truncated=truncated,
    )


def test_preview_exposes_sections_assets_references_and_warnings() -> None:
    preview = PromptPreviewService().create(_profiled(truncated=True))

    section = preview.section(PromptSectionKind.ENVIRONMENT)
    assert section is not None
    assert section.canonical_asset_ids == ("CAP-SHP-IRON-HORIZON",)
    assert section.reference_ids == ("REF-SHP-IRON-HORIZON-01",)
    assert preview.canonical_asset_count == 1
    assert preview.reference_count == 1
    assert "Positive prompt exceeds" in preview.warnings[0]
    assert "No negative prompt" in preview.warnings[1]


def test_preview_formatter_is_deterministic() -> None:
    service = PromptPreviewService()
    preview = service.create(_profiled())

    report = service.format(preview)

    assert report.startswith("Prompt preview: GRAPH-001:prompt")
    assert "POSITIVE PROMPT" in report
    assert "[Environment]" in report
    assert "Approved references: 1" in report
