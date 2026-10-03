from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from vscs.application.production_execution import (
    GovernedInternalRenderSpanCompiler,
    ProviderTemporalSpanExecution,
    ProviderTemporalSpanExecutionCompiler,
    ProviderTemporalSpanExecutionError,
    ProviderTemporalSpanExecutionPlan,
    TimedCanonicalReferenceActivationCompiler,
)
from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)


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
                asset_id="CAP-PLN-002",
                asset_kind=TimedAssetKind.ENVIRONMENT,
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
                canonical_reference_ids=("REF-ROS-PRIMARY",),
            ),
        ),
    )


def _reference(reference_id: str, role: str, asset_id: str) -> dict[str, object]:
    return {
        "reference_id": reference_id,
        "role": role,
        "asset_id": asset_id,
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
            _reference("REF-JAMES-PRIMARY", "primary_identity", "CAP-CHR-001"),
            _reference("REF-SANDRA-PRIMARY", "secondary_identity", "CAP-CHR-003"),
            _reference(
                "REF-IRON-HORIZON-BRIDGE",
                "environment_reference",
                "CAP-LOC-021",
            ),
            _reference("REF-XORIX", "environment_reference", "CAP-PLN-002"),
            _reference("REF-ROS-PRIMARY", "secondary_identity", "CAP-CHR-005"),
        ],
        "diagnostics": [],
    }


def _compiled() -> CompiledProductionPackage:
    timed = _timed()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        _reference_plan(),
    )
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
    )


def test_sht002_contract_enforces_exact_temporal_reference_isolation() -> None:
    plan = ProviderTemporalSpanExecutionCompiler().compile(_compiled())

    assert plan.frame_count == 144
    assert plan.execution_count == 2
    first, second = plan.executions

    assert (first.global_start_frame, first.global_through_frame) == (0, 95)
    assert first.governed_frame_count == 96
    assert first.opening_authority_kind == "shot_opening_authority"
    assert first.opening_frame_global_index == 0
    assert "REF-ROS-PRIMARY" not in first.active_reference_ids
    assert "REF-ROS-PRIMARY" in first.future_reference_ids

    assert (second.global_start_frame, second.global_through_frame) == (96, 143)
    assert second.governed_frame_count == 48
    assert second.opening_authority_kind == "governed_introduction_keyframe_required"
    assert second.opening_frame_global_index == 96
    assert "REF-ROS-PRIMARY" in second.active_reference_ids
    assert second.introduced_reference_ids == ("REF-ROS-PRIMARY",)
    assert second.future_reference_ids == ()


def test_execution_rejects_future_reference_leakage() -> None:
    first = ProviderTemporalSpanExecutionCompiler().compile(_compiled()).executions[0]

    with pytest.raises(
        ProviderTemporalSpanExecutionError,
        match="Future references must be structurally absent",
    ):
        replace(
            first,
            active_reference_ids=(*first.active_reference_ids, "REF-ROS-PRIMARY"),
        )


def test_execution_plan_round_trips_with_deterministic_identity() -> None:
    original = ProviderTemporalSpanExecutionCompiler().compile(_compiled())

    restored = ProviderTemporalSpanExecutionPlan.from_dict(original.to_dict())

    assert restored == original
    assert restored.plan_id == original.plan_id
    assert restored.fingerprint == original.fingerprint


def test_execution_plan_detects_persisted_reference_tampering() -> None:
    original = ProviderTemporalSpanExecutionCompiler().compile(_compiled())
    payload = deepcopy(original.to_dict())
    executions = payload["executions"]
    assert isinstance(executions, list)
    first = executions[0]
    assert isinstance(first, dict)
    active = first["active_reference_ids"]
    assert isinstance(active, list)
    active.append("REF-ROS-PRIMARY")

    with pytest.raises(ProviderTemporalSpanExecutionError):
        ProviderTemporalSpanExecutionPlan.from_dict(payload)


def test_execution_plan_fails_closed_when_package_fingerprint_changes() -> None:
    compiled = _compiled()
    plan = ProviderTemporalSpanExecutionCompiler().compile(compiled)
    changed = replace(compiled, package_fingerprint="changed-package")

    with pytest.raises(
        ProviderTemporalSpanExecutionError,
        match="source package fingerprint changed",
    ):
        plan.require_source(changed)


def test_execution_plan_fails_closed_when_activation_authority_changes() -> None:
    compiled = _compiled()
    plan = ProviderTemporalSpanExecutionCompiler().compile(compiled)
    activation = deepcopy(compiled.timed_reference_activation)
    assert isinstance(activation, dict)
    activations = activation["activations"]
    assert isinstance(activations, list)
    second = activations[1]
    assert isinstance(second, dict)
    second["active_reference_ids"] = [
        reference_id
        for reference_id in second["active_reference_ids"]
        if reference_id != "REF-ROS-PRIMARY"
    ]
    changed = replace(compiled, timed_reference_activation=activation)

    with pytest.raises(
        ProviderTemporalSpanExecutionError,
        match="source authority is invalid",
    ):
        plan.require_source(changed)


def test_compiler_rejects_missing_timed_reference_activation() -> None:
    compiled = replace(_compiled(), timed_reference_activation=None)

    with pytest.raises(
        ProviderTemporalSpanExecutionError,
        match="Timed Canonical Reference Activation",
    ):
        ProviderTemporalSpanExecutionCompiler().compile(compiled)


def test_execution_record_rejects_wrong_opening_semantics() -> None:
    second = ProviderTemporalSpanExecutionCompiler().compile(_compiled()).executions[1]

    with pytest.raises(
        ProviderTemporalSpanExecutionError,
        match="opening authority kind",
    ):
        ProviderTemporalSpanExecution(
            shot_id=second.shot_id,
            span_id=second.span_id,
            sequence_number=second.sequence_number,
            global_start_frame=second.global_start_frame,
            global_through_frame=second.global_through_frame,
            governed_frame_count=second.governed_frame_count,
            active_asset_ids=second.active_asset_ids,
            active_reference_ids=second.active_reference_ids,
            introduced_reference_ids=second.introduced_reference_ids,
            removed_reference_ids=second.removed_reference_ids,
            future_reference_ids=second.future_reference_ids,
            opening_authority_kind="shot_opening_authority",
            opening_frame_global_index=second.opening_frame_global_index,
            assembly_sequence=second.assembly_sequence,
            source_package_fingerprint=second.source_package_fingerprint,
            source_span_plan_fingerprint=second.source_span_plan_fingerprint,
            source_activation_plan_fingerprint=second.source_activation_plan_fingerprint,
        )
