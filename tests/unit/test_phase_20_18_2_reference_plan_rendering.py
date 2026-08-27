from __future__ import annotations

import json
from pathlib import Path

import pytest

from vscs.application.acpp import (
    ReferenceClass,
    ReferenceCoverage,
    ReferencePlan,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
)
from vscs.application.production_execution import (
    CompiledProductionPackage,
    ReferencePlanRenderBindingError,
    ReferencePlanRenderRequestBinder,
)
from vscs.application.rendering import WorkflowInputKind
from vscs.infrastructure.rendering import (
    LTX23VideoStudioDeploymentValidator,
    LTX23VideoStudioInputResolver,
)


def _package() -> CompiledProductionPackage:
    return CompiledProductionPackage(
        task_id="TASK-001",
        production_id="PROD-001",
        episode_id="E01",
        scene_id="S01",
        shot_id="SH01",
        profile="production",
        authority_id="AUTH-001",
        authority_revision=1,
        authority_fingerprint="authority-fingerprint",
        approved_by="human:operator",
        source_package_id="PKG-001",
        source_package_fingerprint="source-fingerprint",
        source_schema_version="1.0",
        universal_text="James, Cheryl and Ros talk inside the room.",
        positive_prompt="James, Cheryl and Ros talk inside the room.",
        negative_prompt="identity drift; redesigned wardrobe",
        previous_approved_final_frame=None,
        filename_prefix="PROD-001/E01/TASK-001",
        width=1280,
        height=720,
        frame_count=121,
        frames_per_second=25,
        cfg=1.0,
        ic_lora_strength=1.0,
        seed=424242,
        composition_plan={},
        production_authority={},
        package_fingerprint="package-fingerprint-1234567890",
    )


def _reference(
    reference_id: str,
    role: ReferenceRole,
    *,
    asset_id: str | None = None,
    width: int = 1280,
    height: int = 720,
    full_asset: bool = True,
) -> ShotReference:
    return ShotReference(
        reference_id=reference_id,
        asset_id=asset_id,
        role=role,
        reference_class=(
            ReferenceClass.SHOT_COMPOSITE
            if role is ReferenceRole.SCENE_COMPOSITION_ANCHOR
            else ReferenceClass.PROVIDER_READY_DERIVATIVE
        ),
        priority=ReferencePriority.REQUIRED,
        subject_type=(
            ReferenceSubjectType.MULTI_SUBJECT_SCENE
            if role is ReferenceRole.SCENE_COMPOSITION_ANCHOR
            else ReferenceSubjectType.CHARACTER
        ),
        source_path=f"references/{reference_id}.png",
        canonical_source_id=f"{asset_id}-MASTER" if asset_id else None,
        width=width,
        height=height,
        provider_ready=True,
        provider_profiles=("production-video-16x9",),
        coverage=ReferenceCoverage(
            framing_type="full_body",
            coverage="full_body",
            required_features_visible=True,
            identity_visible=True,
            full_required_asset_visible=full_asset,
        ),
    )


def _plan(*references: ShotReference, width: int = 1280, height: int = 720) -> ReferencePlan:
    return ReferencePlan(
        target=ReferenceTarget(
            width=width,
            height=height,
            profile_id="production-video-16x9",
            provider_id="ltx23-local",
        ),
        references=references,
    )


def test_multi_reference_plan_binds_to_ltx_render_request() -> None:
    composition = _reference("REF-COMPOSITION", ReferenceRole.SCENE_COMPOSITION_ANCHOR)
    james = _reference("REF-JAMES", ReferenceRole.PRIMARY_IDENTITY, asset_id="CAP-CHR-001")
    cheryl = _reference("REF-CHERYL", ReferenceRole.SECONDARY_IDENTITY, asset_id="CAP-CHR-002")
    ros = _reference("REF-ROS", ReferenceRole.SECONDARY_IDENTITY, asset_id="CAP-CHR-003")

    result = ReferencePlanRenderRequestBinder().bind(
        _package(),
        _plan(composition, james, cheryl, ros),
    )

    assert result.request.workflow_id == "ltx23_production_v1"
    assert result.request.render.width == 1280
    assert result.request.render.height == 720
    assert result.start_reference_id == "REF-COMPOSITION"
    assert result.request.metadata["start_frame"] == "references/REF-COMPOSITION.png"
    assert json.loads(result.request.metadata["reference_images"]) == [
        "references/REF-JAMES.png",
        "references/REF-CHERYL.png",
        "references/REF-ROS.png",
    ]
    assert result.request.assets.asset_ids == (
        "CAP-CHR-001",
        "CAP-CHR-002",
        "CAP-CHR-003",
    )
    assert result.supporting_reference_ids == ("REF-JAMES", "REF-CHERYL", "REF-ROS")


def test_reference_plan_target_must_match_video_dimensions() -> None:
    james = _reference("REF-JAMES", ReferenceRole.PRIMARY_IDENTITY, asset_id="CAP-CHR-001")

    with pytest.raises(ReferencePlanRenderBindingError, match="target dimensions"):
        ReferencePlanRenderRequestBinder().bind(
            _package(),
            _plan(james, width=1024, height=1536),
        )


def test_incomplete_required_reference_is_blocked_before_provider() -> None:
    james = _reference(
        "REF-JAMES-CROPPED",
        ReferenceRole.PRIMARY_IDENTITY,
        asset_id="CAP-CHR-001",
        full_asset=False,
    )

    with pytest.raises(ReferencePlanRenderBindingError, match="extrapolation"):
        ReferencePlanRenderRequestBinder().bind(_package(), _plan(james))


def test_ltx_video_studio_resolver_decodes_multi_reference_array() -> None:
    james = _reference("REF-JAMES", ReferenceRole.PRIMARY_IDENTITY, asset_id="CAP-CHR-001")
    cheryl = _reference("REF-CHERYL", ReferenceRole.SECONDARY_IDENTITY, asset_id="CAP-CHR-002")
    binding = ReferencePlanRenderRequestBinder().bind(_package(), _plan(james, cheryl))

    values = LTX23VideoStudioInputResolver().resolve(binding.request)

    assert values[WorkflowInputKind.START_FRAME] == "references/REF-JAMES.png"
    assert values[WorkflowInputKind.REFERENCE_IMAGES] == ["references/REF-CHERYL.png"]


def test_ltx_video_studio_deployment_validator_requires_real_api_workflow(tmp_path: Path) -> None:
    findings = LTX23VideoStudioDeploymentValidator(tmp_path).validate()

    assert len(findings) == 1
    assert "Video Studio Production API workflow is not installed" in findings[0]
