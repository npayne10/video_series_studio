"""Tests for renderer-neutral ACPP render job compilation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.acpp import (
    ACPPResolutionResult,
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    CompiledProductionPrompt,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    RenderCapability,
    RenderJobCompilationError,
    RenderJobCompiler,
    RenderJobCompilerConfig,
    RenderQualityMode,
    RenderSpecification,
    ResolutionDiagnostic,
    ResolutionSeverity,
    RetryPolicy,
    SeedPolicy,
)


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
            quality_mode=RenderQualityMode.PRODUCTION,
            seed_policy=SeedPolicy.FIXED,
            fixed_seed=1442,
        ),
        assets=(
            AssetBinding(
                asset_id="CHR-JAMES",
                role=AssetBindingRole.SUBJECT,
                canonical_reference_ids=("REF-JAMES-PRIMARY",),
            ),
        ),
        prompt=PromptSpecification(
            positive_visual_intent="James holds position.",
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
        metadata={"source": "ssie"},
    )


def _resolution(*, passed: bool = True) -> ACPPResolutionResult:
    diagnostics = ()
    if not passed:
        diagnostics = (
            ResolutionDiagnostic(
                severity=ResolutionSeverity.ERROR,
                code="ASSET_NOT_RESOLVED",
                message="Asset missing.",
                resource_id="CHR-JAMES",
            ),
        )
    return ACPPResolutionResult(package=_package(), diagnostics=diagnostics)


def _prompt(*, clip_id: str | None = None) -> CompiledProductionPrompt:
    return CompiledProductionPrompt(
        clip_id=clip_id or _package().identity.clip_id,
        schema_version="1.0",
        positive_prompt="James holds position on the bridge.",
        negative_prompt="No identity drift.",
        sections=(),
        canonical_reference_ids=("REF-JAMES-PRIMARY",),
        prompt_package_ids=("PRM-COMMAND-STANCE",),
        start_reference_id="FRAME-SH003-END",
        end_reference_id="FRAME-SH004-END",
        provenance=(),
        checksum="prompt-checksum",
    )


def test_compiler_transfers_render_and_prompt_fields() -> None:
    job = RenderJobCompiler().compile(_resolution(), _prompt())

    assert job.job_id == "JOB-PROD-XORIX-SC002-SH004-CL001"
    assert job.width == 1920
    assert job.height == 800
    assert job.frames_per_second == 24
    assert job.frame_count == 240
    assert job.positive_prompt.startswith("James holds position")
    assert job.negative_prompt == "No identity drift."
    assert job.fixed_seed == 1442


def test_compiler_maps_reference_roles_and_capabilities() -> None:
    job = RenderJobCompiler().compile(_resolution(), _prompt())
    references = {(item.reference_id, item.role) for item in job.input_references}

    assert ("REF-JAMES-PRIMARY", "canonical") in references
    assert ("FRAME-SH003-END", "start_frame") in references
    assert ("FRAME-SH004-END", "end_frame") in references
    assert RenderCapability.CANONICAL_REFERENCE_CONDITIONING in (
        job.required_capabilities
    )
    assert RenderCapability.START_FRAME_CONDITIONING in job.required_capabilities
    assert RenderCapability.END_FRAME_CONDITIONING in job.required_capabilities
    assert RenderCapability.NEGATIVE_PROMPT in job.required_capabilities
    assert RenderCapability.DETERMINISTIC_SEED in job.required_capabilities


def test_compiler_preserves_dependencies_output_and_checksums() -> None:
    compiler = RenderJobCompiler()
    job = compiler.compile(_resolution(), _prompt())

    assert job.dependencies == ("PROD-XORIX-SC002-SH003-CL001",)
    assert job.output_path.endswith("PROD-XORIX-SC002-SH004-CL001.mp4")
    assert len(job.package_checksum) == 64
    assert job.prompt_checksum == "prompt-checksum"
    assert compiler.checksum(job) == compiler.checksum(job)


def test_custom_retry_policy_is_applied() -> None:
    policy = RetryPolicy(maximum_attempts=5, backoff_seconds=2.5)
    compiler = RenderJobCompiler(RenderJobCompilerConfig(retry_policy=policy))

    job = compiler.compile(_resolution(), _prompt())

    assert job.retry_policy == policy


def test_compiler_rejects_failed_resolution() -> None:
    with pytest.raises(RenderJobCompilationError, match="failed resource"):
        RenderJobCompiler().compile(_resolution(passed=False), _prompt())


def test_compiler_rejects_prompt_for_different_clip() -> None:
    with pytest.raises(RenderJobCompilationError, match="does not match"):
        RenderJobCompiler().compile(
            _resolution(),
            replace(_prompt(), clip_id="OTHER-CLIP"),
        )
