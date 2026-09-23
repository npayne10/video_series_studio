from __future__ import annotations

from copy import deepcopy

import pytest

from vscs.application.production_execution import (
    GovernedInternalRenderSpanCompiler,
    TimedCanonicalReferenceActivationCompiler,
    TimedCanonicalReferenceActivationError,
    TimedCanonicalReferenceActivationPlan,
)
from vscs.application.production_execution.package_compilation import (
    CompiledProductionPackage,
    ProductionPackageCompilationError,
    ProductionPackageCompilerService,
)
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)


def _timed_plan() -> TimedAssetPresencePlan:
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


def _reference_plan(*, extra: tuple[dict[str, object], ...] = ()) -> dict[str, object]:
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
            *extra,
        ],
        "diagnostics": [],
    }


def _activation_plan() -> TimedCanonicalReferenceActivationPlan:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    return TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        _reference_plan(),
    )


def _compiled_package(
    timed: dict[str, object],
    spans: dict[str, object],
    activation: dict[str, object] | None,
    references: dict[str, object],
) -> CompiledProductionPackage:
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
        package_fingerprint="placeholder",
        timed_asset_presence=timed,
        internal_render_spans=spans,
        timed_reference_activation=activation,
        reference_plan=references,
    )


def test_ros_reference_is_absent_before_frame_96_and_active_after_introduction() -> None:
    plan = _activation_plan()

    assert plan.activation_count == 2
    first, second = plan.activations

    assert (first.start_frame, first.through_frame) == (0, 95)
    assert first.active_reference_ids == (
        "REF-JAMES-PRIMARY",
        "REF-SANDRA-PRIMARY",
        "REF-IRON-HORIZON-BRIDGE",
    )
    assert "REF-ROS-PRIMARY" not in first.active_reference_ids

    assert (second.start_frame, second.through_frame) == (96, 143)
    assert second.active_reference_ids == (
        "REF-JAMES-PRIMARY",
        "REF-SANDRA-PRIMARY",
        "REF-IRON-HORIZON-BRIDGE",
        "REF-ROS-PRIMARY",
    )
    assert second.introduced_reference_ids == ("REF-ROS-PRIMARY",)
    assert second.removed_reference_ids == ()


def test_frame_state_reference_is_audited_but_never_timed_as_canonical_support() -> None:
    plan = _activation_plan()

    assert plan.frame_state_reference_ids == ("REF-COMPOSITION",)
    assert all(
        "REF-COMPOSITION" not in activation.active_reference_ids
        for activation in plan.activations
    )


def test_reference_asset_identity_mismatch_fails_closed() -> None:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    references = _reference_plan()
    raw = references["references"]
    assert isinstance(raw, list)
    ros = next(
        item
        for item in raw
        if isinstance(item, dict) and item["reference_id"] == "REF-ROS-PRIMARY"
    )
    ros["asset_id"] = "CAP-CHR-001"

    with pytest.raises(TimedCanonicalReferenceActivationError, match="belongs to"):
        TimedCanonicalReferenceActivationCompiler().compile(timed, spans, references)


def test_missing_timed_canonical_reference_fails_closed() -> None:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    references = _reference_plan()
    raw = references["references"]
    assert isinstance(raw, list)
    references["references"] = [
        item
        for item in raw
        if not isinstance(item, dict) or item.get("reference_id") != "REF-ROS-PRIMARY"
    ]

    with pytest.raises(TimedCanonicalReferenceActivationError, match="absent"):
        TimedCanonicalReferenceActivationCompiler().compile(timed, spans, references)


def test_dynamic_unscoped_supporting_reference_fails_closed() -> None:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    extra = _reference("REF-UNSCOPED-STYLE", "style_reference", None)

    with pytest.raises(TimedCanonicalReferenceActivationError, match="cannot infer temporal scope"):
        TimedCanonicalReferenceActivationCompiler().compile(
            timed,
            spans,
            _reference_plan(extra=(extra,)),
        )


def test_activation_round_trip_preserves_identity_and_fingerprint() -> None:
    original = _activation_plan()

    restored = TimedCanonicalReferenceActivationPlan.from_dict(original.to_dict())

    assert restored == original
    assert restored.plan_id == original.plan_id
    assert restored.fingerprint == original.fingerprint


def test_activation_detects_reference_set_tampering() -> None:
    payload = _activation_plan().to_dict()
    tampered = deepcopy(payload)
    activations = tampered["activations"]
    assert isinstance(activations, list)
    first = activations[0]
    assert isinstance(first, dict)
    active = first["active_reference_ids"]
    assert isinstance(active, list)
    active.append("REF-ROS-PRIMARY")

    with pytest.raises(TimedCanonicalReferenceActivationError):
        TimedCanonicalReferenceActivationPlan.from_dict(tampered)


def test_activation_becomes_stale_when_reference_plan_content_changes() -> None:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    references = _reference_plan()
    plan = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        references,
    )
    changed = deepcopy(references)
    raw = changed["references"]
    assert isinstance(raw, list)
    first = raw[1]
    assert isinstance(first, dict)
    first["file_checksum"] = "changed-after-compilation"

    with pytest.raises(TimedCanonicalReferenceActivationError, match="ReferencePlan changed"):
        plan.require_sources(timed, spans, changed)


def test_execution_compiler_derives_timed_reference_activation() -> None:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)

    payload = ProductionPackageCompilerService._timed_reference_activation(
        timed.to_dict(),
        spans.to_dict(),
        _reference_plan(),
    )

    assert payload is not None
    activations = payload["activations"]
    assert isinstance(activations, list)
    assert "REF-ROS-PRIMARY" not in activations[0]["active_reference_ids"]
    assert "REF-ROS-PRIMARY" in activations[1]["active_reference_ids"]


def test_execution_compiler_rejects_timed_reference_without_reference_plan() -> None:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)

    with pytest.raises(ProductionPackageCompilationError, match="absent from the governed ReferencePlan"):
        ProductionPackageCompilerService._timed_reference_activation(
            timed.to_dict(),
            spans.to_dict(),
            None,
        )


def test_compiled_package_serializes_timed_reference_activation_authority() -> None:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        _reference_plan(),
    )

    payload = _compiled_package(
        timed.to_dict(),
        spans.to_dict(),
        activation.to_dict(),
        _reference_plan(),
    ).to_dict()

    assert payload["timed_reference_activation"] == activation.to_dict()


def test_provider_boundary_validates_activation_then_stays_fail_closed_for_orchestration() -> None:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    references = _reference_plan()
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        references,
    )

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match="20.18.2.3.3 compiled timed canonical-reference activation successfully",
    ):
        LocalProductionPackageCompilationService._comfyui_payload(
            _compiled_package(
                timed.to_dict(),
                spans.to_dict(),
                activation.to_dict(),
                references,
            )
        )


def test_provider_boundary_preserves_3_2_fail_closed_contract_when_activation_missing() -> None:
    timed = _timed_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match="current provider execution is still monolithic",
    ):
        LocalProductionPackageCompilationService._comfyui_payload(
            _compiled_package(
                timed.to_dict(),
                spans.to_dict(),
                None,
                _reference_plan(),
            )
        )
