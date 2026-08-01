"""Tests for provider-neutral ACPP prompt compilation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.acpp import (
    ACPPPromptCompiler,
    ACPPResolutionResult,
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    ContinuityBinding,
    OutputSpecification,
    PromptCompilationError,
    PromptCompilerConfig,
    PromptContribution,
    PromptSpecification,
    RenderSpecification,
    ResolutionDiagnostic,
    ResolutionProvenance,
    ResolutionSeverity,
)


class ContributionCatalog:
    """Deterministic prompt contribution catalog used by tests."""

    def __init__(self, values: dict[str, PromptContribution]) -> None:
        self.values = values

    def resolve_prompt_package(self, package_id: str) -> PromptContribution | None:
        return self.values.get(package_id)


def _package() -> ClipProductionPackage:
    return ClipProductionPackage(
        identity=ClipIdentity(
            clip_id="PROD-XORIX-SC002-SH004-CL001",
            production_id="PROD-XORIX",
            episode_id="EP-001",
            scene_id="SCN-002",
            shot_id="SCN-002-S004",
        ),
        render=RenderSpecification(
            width=1920,
            height=800,
            frames_per_second=24,
            frame_count=240,
        ),
        assets=(
            AssetBinding(
                asset_id="LOC-MAURITANIA-BRIDGE",
                role=AssetBindingRole.LOCATION,
                canonical_reference_ids=("REF-BRIDGE-PRIMARY",),
            ),
            AssetBinding(
                asset_id="CHR-JAMES",
                role=AssetBindingRole.SUBJECT,
                canonical_reference_ids=("REF-JAMES-PRIMARY",),
                behaviour_package_ids=("BHV-COMMAND-PRESENCE",),
            ),
        ),
        prompt=PromptSpecification(
            positive_visual_intent="James holds position at the command console.",
            negative_constraints=(
                "No exaggerated holographic glow.",
                "No unapproved costume changes.",
            ),
            camera_language="Medium close coverage with restrained push-in.",
            lighting_intent="Maintain tense night bridge lighting.",
            behaviour_intent="James remains disciplined and controlled.",
            environment_intent="Operational Mauritania bridge at night.",
            continuity_intent="Preserve James's established screen position.",
        ),
        continuity=ContinuityBinding(
            incoming_clip_id="PROD-XORIX-SC002-SH003-CL001",
            start_reference_id="FRAME-SH003-END",
            end_reference_id="FRAME-SH004-END",
            requirements=("Maintain established screen direction.",),
            outgoing_state=("James remains at the console.",),
        ),
        audio=AudioSpecification(),
        output=OutputSpecification(
            relative_directory="production/EP-001/SCN-002",
            filename_stem="PROD-XORIX-SC002-SH004-CL001",
        ),
        metadata={"resolution.status": "resolved"},
    )


def _resolution(*, passed: bool = True) -> ACPPResolutionResult:
    diagnostics = ()
    if not passed:
        diagnostics = (
            ResolutionDiagnostic(
                severity=ResolutionSeverity.ERROR,
                code="ASSET_NOT_RESOLVED",
                message="Required asset was not resolved.",
                resource_id="CHR-JAMES",
            ),
        )
    return ACPPResolutionResult(
        package=_package(),
        diagnostics=diagnostics,
        provenance=(
            ResolutionProvenance(
                resource_id="CAP-CHR-001",
                resource_type="cap",
                version="3.1",
                source="catalog",
                checksum="cap-checksum",
            ),
            ResolutionProvenance(
                resource_id="PRM-COMMAND-STANCE",
                resource_type="prompt_package",
                version="1.2",
                source="assets/behaviours/command/prompts/stance",
                checksum="prompt-checksum",
            ),
        ),
    )


def _catalog() -> ContributionCatalog:
    return ContributionCatalog(
        {
            "PRM-COMMAND-STANCE": PromptContribution(
                package_id="PRM-COMMAND-STANCE",
                version="1.2",
                positive_fragments=(
                    "Grounded hard-science-fiction performance.",
                ),
                negative_fragments=("No theatrical gesturing.",),
                behaviour_fragments=(
                    "Use economical movement and controlled posture.",
                ),
                source="assets/behaviours/command/prompts/stance",
                checksum="prompt-checksum",
            )
        }
    )


def test_compiler_builds_ordered_provider_neutral_sections() -> None:
    compiled = ACPPPromptCompiler(_catalog()).compile(_resolution())

    assert [section.name for section in compiled.sections] == [
        "visual_intent",
        "canonical_assets",
        "canonical_references",
        "environment",
        "camera",
        "lighting",
        "behaviour",
        "prompt_packages",
        "continuity",
        "negative_constraints",
    ]
    assert compiled.positive_prompt.startswith(
        "James holds position at the command console."
    )
    assert "Medium close coverage" in compiled.positive_prompt
    assert "Grounded hard-science-fiction performance" in compiled.positive_prompt


def test_compiler_preserves_reference_and_frame_constraints() -> None:
    compiled = ACPPPromptCompiler(_catalog()).compile(_resolution())

    assert compiled.canonical_reference_ids == (
        "REF-BRIDGE-PRIMARY",
        "REF-JAMES-PRIMARY",
    )
    assert compiled.start_reference_id == "FRAME-SH003-END"
    assert compiled.end_reference_id == "FRAME-SH004-END"
    continuity = next(
        section.content
        for section in compiled.sections
        if section.name == "continuity"
    )
    assert "Use start reference FRAME-SH003-END" in continuity
    assert "Produce end reference FRAME-SH004-END" in continuity


def test_compiler_merges_and_deduplicates_negative_constraints() -> None:
    compiled = ACPPPromptCompiler(_catalog()).compile(_resolution())

    assert compiled.negative_prompt == (
        "No exaggerated holographic glow.; "
        "No unapproved costume changes.; "
        "No theatrical gesturing."
    )


def test_checksum_is_deterministic_and_content_sensitive() -> None:
    compiler = ACPPPromptCompiler(_catalog())
    resolution = _resolution()

    first = compiler.compile(resolution)
    second = compiler.compile(resolution)
    changed_package = replace(
        resolution.package,
        prompt=replace(
            resolution.package.prompt,
            lighting_intent="Maintain low-key emergency lighting.",
        ),
    )
    changed = compiler.compile(replace(resolution, package=changed_package))

    assert first.checksum == second.checksum
    assert first.checksum != changed.checksum
    assert len(first.checksum) == 64


def test_failed_resolution_is_rejected_by_default() -> None:
    with pytest.raises(PromptCompilationError, match="failed resource resolution"):
        ACPPPromptCompiler(_catalog()).compile(_resolution(passed=False))


def test_missing_contribution_can_be_optional() -> None:
    compiler = ACPPPromptCompiler(
        ContributionCatalog({}),
        PromptCompilerConfig(require_prompt_contributions=False),
    )

    compiled = compiler.compile(_resolution())

    assert compiled.prompt_package_ids == ("PRM-COMMAND-STANCE",)
    assert all(section.name != "prompt_packages" for section in compiled.sections)
