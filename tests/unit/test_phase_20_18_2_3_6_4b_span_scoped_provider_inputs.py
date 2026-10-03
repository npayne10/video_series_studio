from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.production_execution import (
    GovernedInternalRenderSpanCompiler,
    SpanScopedProviderCompilationError,
    SpanScopedProviderInputCompiler,
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


def _compiled() -> CompiledProductionPackage:
    timed = _timed()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    references = _reference_plan()
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        references,
    )
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
        negative_prompt=(
            "extra people; identity swap; do not duplicate Ros; warped faces"
        ),
        motion_prompt=(
            "James and Sandra remain stable. Ros enters naturally from the left edge."
        ),
        previous_approved_final_frame=None,
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
        reference_plan=references,
    )


def test_sht002_span_scoped_reference_slots_rebuild_picture_indices() -> None:
    plan = SpanScopedProviderInputCompiler().compile(_compiled())
    first, second = plan.spans

    assert tuple(slot.picture_tag for slot in first.reference_slots) == (
        "<Picture 1>",
        "<Picture 2>",
        "<Picture 3>",
        "<Picture 4>",
    )
    assert tuple(slot.reference_id for slot in first.reference_slots) == (
        "REF-JAMES",
        "REF-SANDRA",
        "REF-BRIDGE",
        "REF-XORIX",
    )
    assert "REF-ROS" not in first.active_reference_ids

    assert tuple(slot.picture_tag for slot in second.reference_slots) == (
        "<Picture 1>",
        "<Picture 2>",
        "<Picture 3>",
        "<Picture 4>",
        "<Picture 5>",
    )
    assert tuple(slot.reference_id for slot in second.reference_slots) == (
        "REF-JAMES",
        "REF-SANDRA",
        "REF-BRIDGE",
        "REF-XORIX",
        "REF-ROS",
    )


def test_span_001_removes_ros_semantics_from_every_prompt_channel() -> None:
    first = SpanScopedProviderInputCompiler().compile(_compiled()).spans[0]

    combined = " ".join(
        (first.positive_prompt, first.negative_prompt, first.motion_prompt)
    ).casefold()
    assert "ros" not in combined
    assert "rohsgard" not in combined
    assert "cap-chr-005" not in combined
    assert "ref-ros" not in combined
    assert "james" in combined
    assert "sandra" in combined
    assert "iron horizon bridge" in combined
    assert "xorix" in combined


def test_span_002_contains_ros_and_compact_picture_mapping() -> None:
    second = SpanScopedProviderInputCompiler().compile(_compiled()).spans[1]

    assert "Major Ros Rohsgard" in second.positive_prompt
    assert "<Picture 5> is the authoritative reference for Major Ros Rohsgard." in (
        second.positive_prompt
    )
    assert second.reference_slots[-1].asset_id == "CAP-CHR-005"
    assert second.reference_slots[-1].reference_id == "REF-ROS"
    assert second.omitted_future_aliases == ()


def test_environment_references_remain_stable_across_spans() -> None:
    first, second = SpanScopedProviderInputCompiler().compile(_compiled()).spans

    first_map = {slot.reference_id: slot.picture_tag for slot in first.reference_slots}
    second_map = {slot.reference_id: slot.picture_tag for slot in second.reference_slots}

    assert first_map["REF-BRIDGE"] == "<Picture 3>"
    assert first_map["REF-XORIX"] == "<Picture 4>"
    assert second_map["REF-BRIDGE"] == "<Picture 3>"
    assert second_map["REF-XORIX"] == "<Picture 4>"


def test_reference_slot_fingerprint_changes_when_reference_order_changes() -> None:
    compiled = _compiled()
    original = SpanScopedProviderInputCompiler().compile(compiled)

    activation = dict(compiled.timed_reference_activation or {})
    activations = [dict(item) for item in activation["activations"]]
    first_refs = list(activations[0]["active_reference_ids"])
    activations[0]["active_reference_ids"] = list(reversed(first_refs))
    activation["activations"] = activations
    changed = replace(compiled, timed_reference_activation=activation)

    with pytest.raises(SpanScopedProviderCompilationError, match="source authority is invalid"):
        SpanScopedProviderInputCompiler().compile(changed)

    assert original.spans[0].reference_slot_fingerprint


def test_missing_active_reference_fails_closed() -> None:
    compiled = _compiled()
    references = dict(compiled.reference_plan or {})
    records = [
        item
        for item in references["references"]
        if item["reference_id"] != "REF-XORIX"
    ]
    references["references"] = records
    changed = replace(compiled, reference_plan=references)

    with pytest.raises(SpanScopedProviderCompilationError):
        SpanScopedProviderInputCompiler().compile(changed)


def test_stale_package_fingerprint_fails_closed() -> None:
    compiled = _compiled()
    plan = SpanScopedProviderInputCompiler().compile(compiled)
    changed = replace(compiled, package_fingerprint="changed-package")

    with pytest.raises(
        SpanScopedProviderCompilationError,
        match="source package fingerprint changed",
    ):
        plan.require_source(changed)


def test_picture_slot_declarations_are_deterministic() -> None:
    first_run = SpanScopedProviderInputCompiler().compile(_compiled())
    second_run = SpanScopedProviderInputCompiler().compile(_compiled())

    assert first_run.fingerprint == second_run.fingerprint
    assert first_run.spans[0].prompt_fingerprint == second_run.spans[0].prompt_fingerprint
    assert first_run.spans[0].reference_slot_fingerprint == (
        second_run.spans[0].reference_slot_fingerprint
    )
