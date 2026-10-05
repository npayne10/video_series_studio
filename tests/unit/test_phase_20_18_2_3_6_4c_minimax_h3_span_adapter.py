from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.production_execution import (
    GovernedInternalRenderSpanCompiler,
    GovernedIntroductionKeyframeRequirementCompiler,
    GovernedIntroductionKeyframeStore,
    TimedCanonicalReferenceActivationCompiler,
)
from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)
from vscs.infrastructure.production_execution import (
    MiniMaxH3SpanAdapterCompiler,
    MiniMaxH3SpanAdapterError,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_governed_boundary_registry(
    project: Path,
    *,
    source_shot_id: str = "EP-001-SCN-001-SHT-001",
) -> Path:
    image = project / ".vscs" / "governed_shot_boundaries" / source_shot_id / "GBF-TEST.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"published-governed-shot-boundary")
    registry = project / ".vscs" / "governed_shot_boundaries.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "boundaries": [
                    {
                        "schema_version": "1.0",
                        "boundary_id": "GBF-TEST",
                        "shot_id": source_shot_id,
                        "status": "published",
                        "image_path": image.relative_to(project).as_posix(),
                        "image_sha256": _sha(image),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return image


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
                canonical_reference_ids=("REF-JAMES",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-003",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-SANDRA",),
            ),
            TimedAssetPresence(
                asset_id="CAP-LOC-021",
                asset_kind=TimedAssetKind.LOCATION,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-BRIDGE",),
            ),
            TimedAssetPresence(
                asset_id="CAP-PLN-002",
                asset_kind=TimedAssetKind.PLANET,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-XORIX",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-005",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.ENTER,
                canonical_reference_ids=("REF-ROS",),
            ),
        ),
    )


def _reference(
    reference_id: str,
    asset_id: str,
    role: str,
    label: str,
) -> dict[str, object]:
    return {
        "reference_id": reference_id,
        "asset_id": asset_id,
        "role": role,
        "label": label,
        "reference_class": "provider_ready_derivative",
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
        "references": [
            _reference("REF-JAMES", "CAP-CHR-001", "primary_identity", "Commander James Spence"),
            _reference("REF-SANDRA", "CAP-CHR-003", "secondary_identity", "Sandra Crawford"),
            _reference(
                "REF-BRIDGE",
                "CAP-LOC-021",
                "environment_reference",
                "Iron Horizon bridge",
            ),
            _reference("REF-XORIX", "CAP-PLN-002", "environment_reference", "Xorix"),
            _reference("REF-ROS", "CAP-CHR-005", "secondary_identity", "Major Ros Rohsgard"),
        ],
        "diagnostics": [],
    }


def _authority() -> tuple[
    TimedAssetPresencePlan,
    object,
    object,
    object,
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


def _compiled(project: Path) -> CompiledProductionPackage:
    timed, spans, activation, requirements = _authority()
    opening = project / "boundaries" / "shot-opening.png"
    opening.parent.mkdir(parents=True, exist_ok=True)
    opening.write_bytes(b"governed-shot-opening")

    assets = [
        {"asset_id": "CAP-CHR-001", "name": "Commander James Spence", "category": "character"},
        {"asset_id": "CAP-CHR-003", "name": "Sandra Crawford", "category": "character"},
        {"asset_id": "CAP-CHR-005", "name": "Major Ros Rohsgard", "category": "character"},
        {"asset_id": "CAP-LOC-021", "name": "Iron Horizon bridge", "category": "location"},
        {"asset_id": "CAP-PLN-002", "name": "Xorix", "category": "planet"},
    ]
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
        positive_prompt=(
            "Create a photorealistic bridge shot. "
            "James remains on the left side of the bridge. "
            "Sandra remains at the right control station. "
            "Ros Rohsgard enters naturally from the far left edge. "
            "Xorix remains visible through the forward display."
        ),
        negative_prompt="extra people; identity swap; do not duplicate Ros; warped faces",
        motion_prompt="James and Sandra remain stable. Ros enters naturally from the left edge.",
        previous_approved_final_frame=str(opening.relative_to(project)),
        filename_prefix="XORIX/EP-001/PT-VIDEO-SHT-002",
        width=1280,
        height=720,
        frame_count=144,
        frames_per_second=24,
        cfg=1.0,
        ic_lora_strength=1.0,
        seed=42,
        composition_plan={"assets": assets},
        production_authority={"assets": assets},
        package_fingerprint="package-fingerprint",
        timed_asset_presence=timed.to_dict(),
        internal_render_spans=spans.to_dict(),
        timed_reference_activation=activation.to_dict(),
        reference_plan=_reference_plan(),
        introduction_keyframe_requirements=requirements.to_dict(),
    )


def _live_shaped_projection_compiled(project: Path) -> CompiledProductionPackage:
    base = _compiled(project)
    timed = TimedAssetPresencePlan(
        shot_id="EP-001-SCN-001-SHT-002",
        frames_per_second=24,
        frame_count=144,
        presences=(
            TimedAssetPresence(
                asset_id="CAP-CHR-001",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-JAMES",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-003",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-SANDRA",),
            ),
            TimedAssetPresence(
                asset_id="CAP-ENV-004",
                asset_kind=TimedAssetKind.ENVIRONMENT,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-ENV",),
            ),
            TimedAssetPresence(
                asset_id="CAP-LOC-021",
                asset_kind=TimedAssetKind.LOCATION,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=(),
            ),
            TimedAssetPresence(
                asset_id="CAP-PLN-002",
                asset_kind=TimedAssetKind.PLANET,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-XORIX",),
            ),
            TimedAssetPresence(
                asset_id="CAP-SHP-002",
                asset_kind=TimedAssetKind.SHIP,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-SHIP",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-005",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.ENTER,
                canonical_reference_ids=("REF-ROS",),
            ),
        ),
    )
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    references = {
        "schema_version": "1.0",
        "status": "passed",
        "references": [
            _reference("REF-JAMES", "CAP-CHR-001", "secondary_identity", "Commander James Spence"),
            _reference("REF-SANDRA", "CAP-CHR-003", "primary_identity", "Sandra Crawford"),
            {
                **_reference(
                    "REF-ENV", "CAP-ENV-004", "environment_reference", "Environment Context"
                ),
                "priority": "preferred",
                "subject_type": "environment",
            },
            {
                **_reference("REF-XORIX", "CAP-PLN-002", "environment_reference", "Xorix"),
                "priority": "preferred",
                "subject_type": "environment",
            },
            {
                **_reference(
                    "REF-SHIP", "CAP-SHP-002", "background_identity", "Iron Horizon exterior"
                ),
                "priority": "preferred",
                "subject_type": "ship",
            },
            _reference("REF-ROS", "CAP-CHR-005", "secondary_identity", "Major Ros Rohsgard"),
            {
                "reference_id": "REF-BRIDGE-COMPOSITION",
                "asset_id": None,
                "canonical_source_id": None,
                "role": "scene_composition_anchor",
                "label": "Shot composition — EP-001-SCN-001-SHT-002",
                "reference_class": "shot_composite",
                "priority": "required",
                "subject_type": "multi_subject_scene",
                "source_path": "references/CAP-LOC-021_V2_1280x720.png",
                "provider_ready": True,
                "file_checksum": "sha-bridge-composition",
                "reference_fingerprint": "fp-bridge-composition",
                "contains_environments": ["CAP-LOC-021"],
                "contains_subjects": [],
                "contains_props": [],
            },
        ],
        "diagnostics": [],
    }
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        references,
    )
    requirements = GovernedIntroductionKeyframeRequirementCompiler().compile(
        spans,
        activation,
    )
    assets = list(base.production_authority["assets"])
    assets.extend(
        [
            {"asset_id": "CAP-ENV-004", "name": "Environment Context", "category": "environment"},
            {"asset_id": "CAP-SHP-002", "name": "Iron Horizon exterior", "category": "ship"},
        ]
    )
    return replace(
        base,
        timed_asset_presence=timed.to_dict(),
        internal_render_spans=spans.to_dict(),
        timed_reference_activation=activation.to_dict(),
        reference_plan=references,
        introduction_keyframe_requirements=requirements.to_dict(),
        production_authority={"assets": assets},
        composition_plan={"assets": assets},
    )


def _approve_intro(project: Path, compiled: CompiledProductionPackage) -> Path:
    raw = compiled.introduction_keyframe_requirements
    assert isinstance(raw, dict)
    from vscs.application.production_execution import IntroductionKeyframeRequirementPlan

    requirements = IntroductionKeyframeRequirementPlan.from_dict(raw)
    requirement = requirements.requirements[0]
    source = project / "boundaries" / "frame-000095.png"
    intro = project / "keyframes" / "frame-000096.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    intro.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"exact-frame-95")
    intro.write_bytes(b"approved-frame-96-with-ros")
    store = GovernedIntroductionKeyframeStore(project)
    record = store.create_record(
        requirement,
        image_path=intro.relative_to(project).as_posix(),
        image_sha256=_sha(intro),
        source_boundary_image_path=source.relative_to(project).as_posix(),
        source_boundary_image_sha256=_sha(source),
        approved_by="Neill Payne",
        approved_at="2026-10-03T12:00:00+02:00",
    )
    store.save(record, requirement)
    return intro


def test_h3_span_adapter_isolates_references_and_uses_only_local_frame_zero_guides(
    tmp_path: Path,
) -> None:
    compiled = _compiled(tmp_path)
    intro = _approve_intro(tmp_path, compiled)

    plan = MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)

    assert plan.provider_id == "minimax-h3-ref2va"
    assert plan.mode == "governed_isolated_span_ref2va"
    assert plan.governed_frame_count == 144
    assert len(plan.spans) == 2
    first, second = plan.spans

    assert (first.global_start_frame, first.global_through_frame) == (0, 95)
    assert first.governed_frame_count == 96
    assert first.provider_frame_count == 103
    assert first.provider_trim_frames == 7
    assert first.guide_frame_idx == 0
    assert first.guide_source_kind == "shot_opening_authority"
    assert "REF-ROS" not in tuple(slot.reference_id for slot in first.reference_slots)
    assert (
        "ros"
        not in " ".join(
            (first.positive_prompt, first.negative_prompt, first.motion_prompt)
        ).casefold()
    )

    assert (second.global_start_frame, second.global_through_frame) == (96, 143)
    assert second.governed_frame_count == 48
    assert second.provider_frame_count == 55
    assert second.provider_trim_frames == 7
    assert second.guide_frame_idx == 0
    assert second.guide_source_kind == "governed_introduction_keyframe"
    assert Path(second.guide_image_path) == intro.resolve(strict=False)
    assert second.guide_image_sha256 == _sha(intro)
    assert "REF-ROS" in tuple(slot.reference_id for slot in second.reference_slots)
    assert second.to_dict()["guide_semantics"] == "frame_state_anchor"
    assert second.to_dict()["temporal_asset_gate"] is False


def test_h3_live_shaped_projection_prefers_required_bridge_composition_anchor(
    tmp_path: Path,
) -> None:
    compiled = _live_shaped_projection_compiled(tmp_path)

    first = MiniMaxH3SpanAdapterCompiler(tmp_path).compile_execution(
        compiled,
        sequence_number=1,
    )

    assert tuple(slot.asset_id for slot in first.reference_slots) == (
        "CAP-CHR-001",
        "CAP-CHR-003",
        "CAP-LOC-021",
        "CAP-PLN-002",
    )
    assert tuple(slot.reference_id for slot in first.reference_slots) == (
        "REF-JAMES",
        "REF-SANDRA",
        "REF-BRIDGE-COMPOSITION",
        "REF-XORIX",
    )
    serialized = " ".join(
        (
            first.positive_prompt,
            first.negative_prompt,
            first.motion_prompt,
            *(slot.reference_id for slot in first.reference_slots),
        )
    ).casefold()
    assert "ref-env" not in serialized
    assert "ref-ship" not in serialized
    assert "ref-ros" not in serialized
    assert "<picture 5>" not in first.positive_prompt.casefold()


def test_h3_live_shaped_projection_fills_five_slots_when_ros_becomes_active(
    tmp_path: Path,
) -> None:
    compiled = _live_shaped_projection_compiled(tmp_path)
    _approve_intro(tmp_path, compiled)

    second = MiniMaxH3SpanAdapterCompiler(tmp_path).compile_execution(
        compiled,
        sequence_number=2,
    )

    assert tuple(slot.asset_id for slot in second.reference_slots) == (
        "CAP-CHR-001",
        "CAP-CHR-003",
        "CAP-CHR-005",
        "CAP-LOC-021",
        "CAP-PLN-002",
    )
    assert tuple(slot.reference_id for slot in second.reference_slots) == (
        "REF-JAMES",
        "REF-SANDRA",
        "REF-ROS",
        "REF-BRIDGE-COMPOSITION",
        "REF-XORIX",
    )
    assert len(second.reference_slots) == 5
    assert "REF-ENV" not in {slot.reference_id for slot in second.reference_slots}
    assert "REF-SHIP" not in {slot.reference_id for slot in second.reference_slots}


def test_h3_provider_grid_reproduces_observed_175_frame_native_class(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    plan = MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)

    for span in plan.spans:
        assert (span.provider_frame_count + 1) % 8 == 0


def test_h3_first_span_can_compile_without_future_introduction_keyframe(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)

    first = MiniMaxH3SpanAdapterCompiler(tmp_path).compile_execution(
        compiled,
        sequence_number=1,
    )

    assert first.sequence_number == 1
    assert (first.global_start_frame, first.global_through_frame) == (0, 95)
    assert first.provider_frame_count == 103
    assert first.governed_frame_count == 96
    assert "REF-ROS" not in tuple(slot.reference_id for slot in first.reference_slots)
    assert (
        "ros"
        not in " ".join(
            (first.positive_prompt, first.negative_prompt, first.motion_prompt)
        ).casefold()
    )


def test_h3_first_span_resolves_published_previous_shot_boundary_when_legacy_path_missing(
    tmp_path: Path,
) -> None:
    compiled = _compiled(tmp_path)
    governed = _write_governed_boundary_registry(tmp_path)
    compiled = replace(
        compiled,
        previous_approved_final_frame=None,
        production_authority={
            **compiled.production_authority,
            "continuity": {
                "shot_boundary_mode": "continuous",
                "inheritance_mode": "previous-shot-closing-state",
                "previous_shot_id": "EP-001-SCN-001-SHT-001",
                "source_shot_id": "EP-001-SCN-001-SHT-001",
            },
        },
    )

    first = MiniMaxH3SpanAdapterCompiler(tmp_path).compile_execution(
        compiled,
        sequence_number=1,
    )

    assert Path(first.guide_image_path) == governed.resolve(strict=False)
    assert first.guide_image_sha256 == _sha(governed)
    assert first.guide_source_kind == "shot_opening_authority"


def test_h3_published_previous_shot_boundary_checksum_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    compiled = _compiled(tmp_path)
    governed = _write_governed_boundary_registry(tmp_path)
    compiled = replace(
        compiled,
        previous_approved_final_frame=None,
        production_authority={
            **compiled.production_authority,
            "continuity": {
                "shot_boundary_mode": "continuous",
                "previous_shot_id": "EP-001-SCN-001-SHT-001",
            },
        },
    )
    governed.write_bytes(b"tampered-after-publication")

    with pytest.raises(
        MiniMaxH3SpanAdapterError,
        match="SHA-256 mismatch",
    ):
        MiniMaxH3SpanAdapterCompiler(tmp_path).compile_execution(
            compiled,
            sequence_number=1,
        )


def test_h3_second_span_single_compile_still_requires_approved_intro(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)

    with pytest.raises(
        MiniMaxH3SpanAdapterError,
        match="no approved Introduction Keyframe",
    ):
        MiniMaxH3SpanAdapterCompiler(tmp_path).compile_execution(
            compiled,
            sequence_number=2,
        )


def test_h3_second_span_requires_approved_introduction_keyframe(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)

    with pytest.raises(
        MiniMaxH3SpanAdapterError,
        match="no approved Introduction Keyframe",
    ):
        MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)


def test_h3_first_span_requires_existing_opening_authority(tmp_path: Path) -> None:
    compiled = replace(_compiled(tmp_path), previous_approved_final_frame=None)
    _approve_intro(tmp_path, compiled)

    with pytest.raises(
        MiniMaxH3SpanAdapterError,
        match="requires governed Shot opening image authority",
    ):
        MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)


def test_h3_opening_authority_checksum_is_pinned(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    plan = MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)
    first = plan.spans[0]

    opening = Path(first.guide_image_path)
    opening.write_bytes(b"mutated-opening")

    with pytest.raises(
        MiniMaxH3SpanAdapterError,
        match="no longer matches governed source authority",
    ):
        plan.require_source(compiled, tmp_path)


def test_h3_plan_rejects_package_fingerprint_change(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    plan = MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)

    with pytest.raises(
        MiniMaxH3SpanAdapterError,
        match="source package fingerprint changed",
    ):
        plan.require_source(replace(compiled, package_fingerprint="changed"), tmp_path)


def test_h3_reference_slots_are_exactly_span_scoped(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    first, second = MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled).spans

    assert tuple(slot.picture_tag for slot in first.reference_slots) == (
        "<Picture 1>",
        "<Picture 2>",
        "<Picture 3>",
        "<Picture 4>",
    )
    assert tuple(slot.picture_tag for slot in second.reference_slots) == (
        "<Picture 1>",
        "<Picture 2>",
        "<Picture 3>",
        "<Picture 4>",
        "<Picture 5>",
    )
    assert first.reference_image_size == "match"
    assert second.reference_image_size == "match"


def test_h3_plan_is_deterministic(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)

    first = MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)
    second = MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)

    assert first.fingerprint == second.fingerprint
    assert first.plan_id == second.plan_id
    assert first.spans[0].reference_slot_fingerprint == (second.spans[0].reference_slot_fingerprint)
    assert first.spans[1].prompt_fingerprint == second.spans[1].prompt_fingerprint
