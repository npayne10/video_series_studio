"""Tests for ACPP production bundle validation and serialization."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.acpp import (
    ACPPResolutionResult,
    ACPPSerializer,
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    CompiledProductionPrompt,
    CompiledPromptSection,
    ContinuityBinding,
    OutputSpecification,
    ProductionBundleSerializer,
    ProductionBundleValidationError,
    ProductionBundleValidator,
    PromptSpecification,
    RenderCapability,
    RenderInputReference,
    RenderJob,
    RenderJobCompiler,
    RenderQualityMode,
    RenderSpecification,
    ResolutionProvenance,
    RetryPolicy,
    SeedPolicy,
)


def _artifacts() -> tuple[
    ACPPResolutionResult,
    CompiledProductionPrompt,
    RenderJob,
    str,
]:
    package = ClipProductionPackage(
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
            quality_mode=RenderQualityMode.PRODUCTION,
            seed_policy=SeedPolicy.DERIVED,
        ),
        assets=(
            AssetBinding(
                asset_id="CHR-JAMES",
                role=AssetBindingRole.SUBJECT,
                canonical_reference_ids=("REF-JAMES-PRIMARY",),
            ),
        ),
        prompt=PromptSpecification(
            positive_visual_intent="James holds position on the bridge.",
        ),
        continuity=ContinuityBinding(
            start_reference_id="FRAME-SH003-END",
            end_reference_id="FRAME-SH004-END",
        ),
        audio=AudioSpecification(),
        output=OutputSpecification(
            relative_directory="production/EP-001/SCN-002",
            filename_stem="PROD-XORIX-SC002-SH004-CL001",
        ),
        dependencies=("PROD-XORIX-SC002-SH003-CL001",),
        metadata={"resolution.status": "resolved"},
    )
    provenance = (
        ResolutionProvenance(
            resource_id="CAP-CHR-001",
            resource_type="cap",
            version="3.1",
            source="database",
            checksum="cap-checksum",
        ),
    )
    resolution = ACPPResolutionResult(package=package, provenance=provenance)
    prompt = CompiledProductionPrompt(
        clip_id=package.identity.clip_id,
        schema_version="1.0",
        positive_prompt="James holds position on the bridge.",
        negative_prompt="No identity drift.",
        sections=(
            CompiledPromptSection(
                name="visual_intent",
                content="James holds position on the bridge.",
            ),
        ),
        canonical_reference_ids=("REF-JAMES-PRIMARY",),
        prompt_package_ids=(),
        start_reference_id="FRAME-SH003-END",
        end_reference_id="FRAME-SH004-END",
        provenance=provenance,
        checksum="prompt-checksum",
    )
    package_checksum = ACPPSerializer().checksum(package)
    job = RenderJob(
        job_id=f"JOB-{package.identity.clip_id}",
        clip_id=package.identity.clip_id,
        width=1920,
        height=800,
        frames_per_second=24,
        frame_count=240,
        quality_mode=RenderQualityMode.PRODUCTION,
        seed_policy=SeedPolicy.DERIVED,
        fixed_seed=None,
        positive_prompt=prompt.positive_prompt,
        negative_prompt=prompt.negative_prompt,
        input_references=(
            RenderInputReference("REF-JAMES-PRIMARY", "canonical"),
            RenderInputReference("FRAME-SH003-END", "start_frame"),
            RenderInputReference("FRAME-SH004-END", "end_frame"),
        ),
        start_reference_id=prompt.start_reference_id,
        end_reference_id=prompt.end_reference_id,
        output_path=package.output.relative_path,
        dependencies=package.dependencies,
        retry_policy=RetryPolicy(),
        required_capabilities=(
            RenderCapability.TEXT_TO_VIDEO,
            RenderCapability.IMAGE_TO_VIDEO,
        ),
        package_checksum=package_checksum,
        prompt_checksum=prompt.checksum,
        metadata=tuple(sorted(package.metadata.items())),
    )
    return resolution, prompt, job, RenderJobCompiler().checksum(job)


def test_bundle_builds_and_validates_complete_artifacts() -> None:
    resolution, prompt, job, job_checksum = _artifacts()
    serializer = ProductionBundleSerializer()

    bundle = serializer.build(
        resolution,
        prompt,
        job,
        render_job_checksum=job_checksum,
        metadata={"source": "phase-13"},
    )

    result = ProductionBundleValidator().validate(bundle)
    assert result.passed is True
    assert result.issues == ()
    assert len(bundle.aggregate_checksum) == 64
    assert bundle.metadata == {"source": "phase-13"}


def test_bundle_json_round_trip_preserves_all_artifacts() -> None:
    resolution, prompt, job, job_checksum = _artifacts()
    serializer = ProductionBundleSerializer()
    bundle = serializer.build(
        resolution,
        prompt,
        job,
        render_job_checksum=job_checksum,
    )

    restored = serializer.loads(serializer.dumps(bundle))

    assert restored == bundle
    assert restored.resolution.provenance == resolution.provenance
    assert restored.render_job.required_capabilities == job.required_capabilities


def test_bundle_rejects_tampered_package_checksum() -> None:
    resolution, prompt, job, job_checksum = _artifacts()
    serializer = ProductionBundleSerializer()
    bundle = serializer.build(
        resolution,
        prompt,
        job,
        render_job_checksum=job_checksum,
    )
    tampered = replace(bundle, package_checksum="incorrect")

    result = ProductionBundleValidator().validate(tampered)

    assert result.passed is False
    assert any(issue.code == "PACKAGE_CHECKSUM_MISMATCH" for issue in result.issues)
    with pytest.raises(ProductionBundleValidationError):
        serializer.dumps(tampered)


def test_bundle_rejects_clip_identity_mismatch() -> None:
    resolution, prompt, job, job_checksum = _artifacts()
    mismatched_prompt = replace(prompt, clip_id="OTHER-CLIP")

    with pytest.raises(ProductionBundleValidationError) as error:
        ProductionBundleSerializer().build(
            resolution,
            mismatched_prompt,
            job,
            render_job_checksum=job_checksum,
        )

    assert any(
        issue.code == "CLIP_ID_MISMATCH" for issue in error.value.result.issues
    )


def test_bundle_rejects_dependency_mismatch() -> None:
    resolution, prompt, job, job_checksum = _artifacts()
    mismatched_job = replace(job, dependencies=())

    with pytest.raises(ProductionBundleValidationError) as error:
        ProductionBundleSerializer().build(
            resolution,
            prompt,
            mismatched_job,
            render_job_checksum=job_checksum,
        )

    assert any(
        issue.code == "DEPENDENCY_MISMATCH" for issue in error.value.result.issues
    )


def test_bundle_report_summarizes_handoff_contract() -> None:
    resolution, prompt, job, job_checksum = _artifacts()
    serializer = ProductionBundleSerializer()
    bundle = serializer.build(
        resolution,
        prompt,
        job,
        render_job_checksum=job_checksum,
    )

    report = serializer.report(bundle)

    assert "Status: PASSED" in report
    assert bundle.package.identity.clip_id in report
    assert job.output_path in report
    assert bundle.aggregate_checksum in report
