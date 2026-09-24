from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from vscs.application.production_execution import (
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeRequirementCompiler,
    GovernedIntroductionKeyframeStore,
    GovernedInternalRenderSpanCompiler,
    GovernedInternalRenderSpanPlan,
    IntroductionKeyframeRequirement,
    IntroductionKeyframeRequirementPlan,
    TimedCanonicalReferenceActivationCompiler,
    TimedCanonicalReferenceActivationPlan,
)
from vscs.application.production_execution.package_compilation import (
    CompiledProductionPackage,
    ProductionPackageCompilerService,
)
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)
from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    CurrentAuthorityLTX25GovernedKeyframeCompilationService,
)
from vscs.infrastructure.production_execution.ltx25_span_conditioning import (
    LTX25SpanConditioningError,
    LTX25SpanProviderConditioningCompiler,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timed() -> TimedAssetPresencePlan:
    return TimedAssetPresencePlan(
        shot_id="EP-001-SCN-001-SHT-002",
        frames_per_second=24,
        frame_count=144,
        presences=(
            TimedAssetPresence(
                asset_id="CAP-CHR-001",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-JAMES-PRIMARY",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-003",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-SANDRA-PRIMARY",),
            ),
            TimedAssetPresence(
                asset_id="CAP-LOC-021",
                asset_kind=TimedAssetKind.LOCATION,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-IRON-HORIZON-BRIDGE",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-004",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.ENTER,
                canonical_reference_ids=("REF-ROS-PRIMARY",),
            ),
        ),
    )


def _reference(
    reference_id: str,
    role: str,
    asset_id: str | None,
) -> dict[str, object]:
    return {
        "reference_id": reference_id,
        "role": role,
        "asset_id": asset_id,
        "reference_class": (
            "shot_composite" if role == "scene_composition_anchor" else "provider_ready_derivative"
        ),
        "priority": "required",
        "subject_type": "character",
        "source_path": f"references/{reference_id}.png",
        "provider_ready": True,
        "file_checksum": f"sha-{reference_id}",
        "reference_fingerprint": f"fp-{reference_id}",
    }


def _reference_plan() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "status": "passed",
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx-2.5",
        },
        "references": [
            _reference("REF-COMPOSITION", "scene_composition_anchor", None),
            _reference("REF-JAMES-PRIMARY", "primary_identity", "CAP-CHR-001"),
            _reference("REF-SANDRA-PRIMARY", "secondary_identity", "CAP-CHR-003"),
            _reference(
                "REF-IRON-HORIZON-BRIDGE",
                "environment_reference",
                "CAP-LOC-021",
            ),
            _reference("REF-ROS-PRIMARY", "secondary_identity", "CAP-CHR-004"),
        ],
        "diagnostics": [],
    }


def _authority() -> tuple[
    TimedAssetPresencePlan,
    GovernedInternalRenderSpanPlan,
    TimedCanonicalReferenceActivationPlan,
    IntroductionKeyframeRequirementPlan,
]:
    timed = _timed()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        _reference_plan(),
    )
    requirements = GovernedIntroductionKeyframeRequirementCompiler().compile(
        spans,
        activation,
    )
    return timed, spans, activation, requirements


def _compiled(
    *,
    requirements: dict[str, object] | None,
) -> CompiledProductionPackage:
    timed, spans, activation, _ = _authority()
    return CompiledProductionPackage(
        task_id="PT-VIDEO-SHT-002",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="EP-001-SCN-001-SHT-002",
        profile="production",
        authority_id="UPD-SHT-002",
        authority_revision=1,
        authority_fingerprint="authority",
        approved_by="Neill Payne",
        source_package_id="PP-SHT-002",
        source_package_fingerprint="source",
        source_schema_version="1.0",
        universal_text="governed",
        positive_prompt="positive",
        negative_prompt="negative",
        previous_approved_final_frame=None,
        filename_prefix="XORIX/EP-001/PT-VIDEO-SHT-002",
        width=1280,
        height=720,
        frame_count=144,
        frames_per_second=24,
        cfg=1.0,
        ic_lora_strength=1.0,
        seed=42,
        composition_plan={},
        production_authority={},
        package_fingerprint="package-fingerprint",
        timed_asset_presence=timed.to_dict(),
        internal_render_spans=spans.to_dict(),
        timed_reference_activation=activation.to_dict(),
        reference_plan=_reference_plan(),
        introduction_keyframe_requirements=requirements,
    )


def _approved_introduction(
    project: Path,
    requirements: IntroductionKeyframeRequirementPlan,
) -> None:
    requirement = requirements.requirements[0]
    source = project / "boundaries" / "span-001-final.png"
    intro = project / "keyframes" / "span-002-introduction.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    intro.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"exact-span-001-final-frame-95")
    intro.write_bytes(b"approved-frame-96-with-ros")
    store = GovernedIntroductionKeyframeStore(project)
    record = store.create_record(
        requirement,
        image_path=intro.relative_to(project).as_posix(),
        image_sha256=_sha(intro),
        source_boundary_image_path=source.relative_to(project).as_posix(),
        source_boundary_image_sha256=_sha(source),
        approved_by="Neill Payne",
        approved_at="2026-09-24T10:30:00+02:00",
    )
    store.save(record, requirement)


def test_frame_96_introduction_requirement_is_exact_and_nonduplicating() -> None:
    _, _, _, plan = _authority()

    assert plan.requirement_count == 1
    requirement = plan.requirements[0]
    assert requirement.source_global_frame_index == 95
    assert requirement.target_global_frame_index == 96
    assert requirement.target_through_frame == 143
    assert requirement.target_frame_count == 48
    assert requirement.introduced_asset_ids == ("CAP-CHR-004",)
    assert requirement.introduced_reference_ids == ("REF-ROS-PRIMARY",)

    semantics = requirement.to_dict()["conditioning_semantics"]
    assert semantics == {
        "conditioning_frame_global_index": 96,
        "conditioning_frame_is_emitted": True,
        "preceding_boundary_frame_global_index": 95,
        "preceding_boundary_frame_reemitted_in_target_span": False,
    }


def test_requirement_round_trip_and_source_reproduction() -> None:
    _, spans, activation, original = _authority()

    restored = IntroductionKeyframeRequirementPlan.from_dict(original.to_dict())
    restored.require_sources(spans, activation)

    assert restored == original
    assert restored.plan_id == original.plan_id
    assert restored.fingerprint == original.fingerprint


def test_human_approved_introduction_keyframe_is_checksum_pinned(tmp_path: Path) -> None:
    _, _, _, requirements = _authority()
    _approved_introduction(tmp_path, requirements)
    requirement = requirements.requirements[0]
    store = GovernedIntroductionKeyframeStore(tmp_path)

    approved = store.require_approved(requirement)

    assert approved.target_global_frame_index == 96
    assert approved.introduced_reference_ids == ("REF-ROS-PRIMARY",)

    image = store.image_path(approved)
    image.write_bytes(b"changed-after-approval")
    with pytest.raises(GovernedIntroductionKeyframeError, match="checksum"):
        store.require_approved(requirement)


def test_introduction_keyframe_fails_when_requirement_changes(tmp_path: Path) -> None:
    _, _, _, requirements = _authority()
    _approved_introduction(tmp_path, requirements)
    requirement = requirements.requirements[0]
    changed = IntroductionKeyframeRequirement(
        shot_id=requirement.shot_id,
        boundary_id=requirement.boundary_id,
        source_span_id=requirement.source_span_id,
        target_span_id=requirement.target_span_id,
        source_global_frame_index=requirement.source_global_frame_index,
        target_global_frame_index=requirement.target_global_frame_index,
        target_through_frame=requirement.target_through_frame,
        active_asset_ids=requirement.active_asset_ids,
        active_reference_ids=requirement.active_reference_ids,
        introduced_asset_ids=requirement.introduced_asset_ids,
        introduced_reference_ids=(),
        source_span_plan_fingerprint=requirement.source_span_plan_fingerprint,
        source_activation_plan_fingerprint=requirement.source_activation_plan_fingerprint,
    )

    with pytest.raises(GovernedIntroductionKeyframeError):
        GovernedIntroductionKeyframeStore(tmp_path).require_approved(changed)


def test_ltx25_conditioning_uses_97_and_49_provider_frames_without_duplicate_95(
    tmp_path: Path,
) -> None:
    _, _, _, requirements = _authority()
    _approved_introduction(tmp_path, requirements)
    compiled = _compiled(requirements=requirements.to_dict())

    plan = LTX25SpanProviderConditioningCompiler(tmp_path).compile(compiled)

    assert plan.governed_frame_count == 144
    assert len(plan.spans) == 2
    first, second = plan.spans

    assert (first.global_start_frame, first.global_through_frame) == (0, 95)
    assert first.governed_frame_count == 96
    assert first.provider_frame_count == 97
    assert first.provider_trim_frames == 1
    assert first.conditioning_source_kind == "shot_opening_authority"

    assert (second.global_start_frame, second.global_through_frame) == (96, 143)
    assert second.governed_frame_count == 48
    assert second.provider_frame_count == 49
    assert second.provider_trim_frames == 1
    assert second.conditioning_source_kind == "governed_introduction_keyframe"
    assert second.conditioning_frame_global_index == 96
    assert second.preceding_boundary_global_frame_index == 95
    assert second.preceding_boundary_frame_reemitted is False
    assert second.conditioning_frame_is_emitted is True
    assert second.introduced_reference_ids == ("REF-ROS-PRIMARY",)
    assert second.direct_provider_reference_ids == ()


def test_candidate_c_exposes_governed_span_conditioning_compilation(
    tmp_path: Path,
) -> None:
    _, _, _, requirements = _authority()
    _approved_introduction(tmp_path, requirements)

    payload = CurrentAuthorityLTX25GovernedKeyframeCompilationService(
        tmp_path
    ).compile_span_provider_conditioning(
        _compiled(requirements=requirements.to_dict())
    )

    assert payload["provider_id"] == "ltx-2.5"
    assert payload["mode"] == "governed_multi_span_keyframe_i2v"
    spans = payload["spans"]
    assert isinstance(spans, list)
    assert spans[1]["introduction_keyframe_id"]
    assert spans[1]["conditioning_frame_global_index"] == 96
    assert spans[1]["preceding_boundary_frame_reemitted"] is False


def test_ltx25_conditioning_fails_closed_without_approved_introduction_keyframe(
    tmp_path: Path,
) -> None:
    _, _, _, requirements = _authority()

    with pytest.raises(LTX25SpanConditioningError, match="no usable governed Introduction Keyframe"):
        LTX25SpanProviderConditioningCompiler(tmp_path).compile(
            _compiled(requirements=requirements.to_dict())
        )


def test_production_package_compiler_derives_introduction_requirements() -> None:
    _, spans, activation, requirements = _authority()

    payload = ProductionPackageCompilerService._introduction_keyframe_requirements(
        spans.to_dict(),
        activation.to_dict(),
    )

    assert payload == requirements.to_dict()
    assert payload is not None
    assert payload["requirement_count"] == 1


def test_compiled_package_serializes_introduction_requirement_authority() -> None:
    _, _, _, requirements = _authority()

    payload = _compiled(requirements=requirements.to_dict()).to_dict()

    assert payload["introduction_keyframe_requirements"] == requirements.to_dict()


def test_generic_monolithic_provider_stays_blocked_after_phase_3_4_authority() -> None:
    _, _, _, requirements = _authority()

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match=r"20\.18\.2\.3\.4 compiled governed Introduction Keyframe requirements",
    ):
        LocalProductionPackageCompilationService._comfyui_payload(
            _compiled(requirements=requirements.to_dict())
        )
