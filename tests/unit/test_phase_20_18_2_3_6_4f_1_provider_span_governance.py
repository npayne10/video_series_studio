from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from vscs.application.production_execution import (
    GovernedInternalRenderSpanCompiler,
    ProviderSpanGovernanceCompiler,
    ProviderSpanGovernanceError,
    ProviderSpanGovernancePlan,
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
                canonical_reference_ids=("REF-ROS",),
            ),
        ),
    )


def _reference(reference_id: str, asset_id: str) -> dict[str, object]:
    return {
        "reference_id": reference_id,
        "role": "identity_or_environment",
        "asset_id": asset_id,
        "reference_class": "provider_ready_derivative",
        "priority": "required",
        "subject_type": "governed",
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
            _reference("REF-JAMES", "CAP-CHR-001"),
            _reference("REF-SANDRA", "CAP-CHR-003"),
            _reference("REF-BRIDGE", "CAP-LOC-021"),
            _reference("REF-XORIX", "CAP-PLN-002"),
            _reference("REF-ROS", "CAP-CHR-005"),
        ],
        "diagnostics": [],
    }


def _compiled() -> CompiledProductionPackage:
    timed = _timed()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    references = _reference_plan()
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        references,
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
        reference_plan=references,
    )


def test_sht002_governance_compiles_local_span_metadata() -> None:
    plan = ProviderSpanGovernanceCompiler().compile(_compiled())
    first, second = plan.spans

    assert (first.global_start_frame, first.global_through_frame) == (0, 95)
    assert (first.local_start_frame, first.local_through_frame) == (0, 95)
    assert first.local_frame_count == 96
    assert first.active_character_asset_ids == ("CAP-CHR-001", "CAP-CHR-003")
    assert first.introduced_character_asset_ids == ()
    assert first.future_character_asset_ids == ("CAP-CHR-005",)
    assert first.exact_active_character_count == 2
    assert first.has_character_introduction is False

    assert (second.global_start_frame, second.global_through_frame) == (96, 143)
    assert (second.local_start_frame, second.local_through_frame) == (0, 47)
    assert second.local_frame_count == 48
    assert second.active_character_asset_ids == (
        "CAP-CHR-001",
        "CAP-CHR-003",
        "CAP-CHR-005",
    )
    assert second.introduced_asset_ids == ("CAP-CHR-005",)
    assert second.introduced_character_asset_ids == ("CAP-CHR-005",)
    assert second.future_character_asset_ids == ()
    assert second.exact_active_character_count == 3
    assert second.has_character_introduction is True


def test_governance_round_trips_with_deterministic_identity() -> None:
    original = ProviderSpanGovernanceCompiler().compile(_compiled())
    restored = ProviderSpanGovernancePlan.from_dict(original.to_dict())

    assert restored == original
    assert restored.plan_id == original.plan_id
    assert restored.fingerprint == original.fingerprint


def test_governance_fails_closed_when_package_changes() -> None:
    compiled = _compiled()
    plan = ProviderSpanGovernanceCompiler().compile(compiled)

    with pytest.raises(
        ProviderSpanGovernanceError,
        match="source package fingerprint changed",
    ):
        plan.require_source(replace(compiled, package_fingerprint="changed-package"))


def test_governance_detects_persisted_character_count_tampering() -> None:
    payload = deepcopy(ProviderSpanGovernanceCompiler().compile(_compiled()).to_dict())
    spans = payload["spans"]
    assert isinstance(spans, list)
    second = spans[1]
    assert isinstance(second, dict)
    second["exact_active_character_count"] = 4

    with pytest.raises(
        ProviderSpanGovernanceError,
        match="Exact active character count",
    ):
        ProviderSpanGovernancePlan.from_dict(payload)


def test_governance_rejects_reference_without_asset_mapping() -> None:
    compiled = _compiled()
    references = deepcopy(compiled.reference_plan)
    assert isinstance(references, dict)
    records = references["references"]
    assert isinstance(records, list)
    ros = next(
        record
        for record in records
        if isinstance(record, dict) and record.get("reference_id") == "REF-ROS"
    )
    assert isinstance(ros, dict)
    ros["asset_id"] = None

    changed = replace(compiled, reference_plan=references)

    with pytest.raises(ProviderSpanGovernanceError):
        ProviderSpanGovernanceCompiler().compile(changed)
