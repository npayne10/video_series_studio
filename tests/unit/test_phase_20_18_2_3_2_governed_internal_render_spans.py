from __future__ import annotations

from copy import deepcopy

import pytest

from vscs.application.production_execution import (
    GovernedInternalRenderSpanCompiler,
    GovernedInternalRenderSpanError,
    GovernedInternalRenderSpanPlan,
)
from vscs.application.production_execution.package_compilation import (
    CompiledProductionPackage,
    ProductionPackageCompilerService,
)
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    AssetPresenceRemoval,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)


def _ros_plan() -> TimedAssetPresencePlan:
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


def _compiled_package(
    timed: dict[str, object] | None,
    spans: dict[str, object] | None,
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
    )


def test_ros_presence_compiles_to_two_exact_internal_render_spans() -> None:
    source = _ros_plan()

    plan = GovernedInternalRenderSpanCompiler().compile(source)

    assert plan.shot_id == source.shot_id
    assert plan.span_count == 2
    assert plan.change_frames == (96,)
    assert len(plan.boundaries) == 1

    first, second = plan.spans
    assert (first.start_frame, first.through_frame, first.frame_count) == (0, 95, 96)
    assert (second.start_frame, second.through_frame, second.frame_count) == (96, 143, 48)

    assert set(first.active_asset_ids) == {
        "CAP-CHR-001",
        "CAP-CHR-003",
        "CAP-LOC-021",
    }
    assert set(second.active_asset_ids) == {
        "CAP-CHR-001",
        "CAP-CHR-003",
        "CAP-LOC-021",
        "CAP-CHR-004",
    }
    assert first.introduced_asset_ids == ()
    assert second.introduced_asset_ids == ("CAP-CHR-004",)
    assert first.removed_asset_ids == ()
    assert second.removed_asset_ids == ()


def test_internal_boundary_links_exact_final_frame_95_to_span_two_frame_zero() -> None:
    plan = GovernedInternalRenderSpanCompiler().compile(_ros_plan())
    first, second = plan.spans
    boundary = plan.boundaries[0]

    assert boundary.source_span_id == first.span_id
    assert boundary.target_span_id == second.span_id
    assert boundary.source_global_frame_index == 95
    assert boundary.target_global_frame_index == 96
    assert boundary.source_local_frame_index == 95
    assert boundary.target_local_frame_index == 0
    assert first.closing_internal_boundary_id == boundary.boundary_id
    assert second.opening_internal_boundary_id == boundary.boundary_id
    assert boundary.to_dict()["status"] == "required"


def test_internal_spans_cover_every_governed_frame_once_without_editorial_split() -> None:
    plan = GovernedInternalRenderSpanCompiler().compile(_ros_plan())

    covered = [
        frame for span in plan.spans for frame in range(span.start_frame, span.through_frame + 1)
    ]

    assert covered == list(range(144))
    assert all(span.shot_id == "EP-001-SCN-001-SHT-002" for span in plan.spans)


def test_static_presence_compiles_to_one_span_and_no_internal_boundary() -> None:
    source = TimedAssetPresencePlan(
        shot_id="SHT-STATIC",
        frames_per_second=24,
        frame_count=144,
        presences=(
            TimedAssetPresence(
                asset_id="CAP-CHR-001",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
            ),
        ),
    )

    plan = GovernedInternalRenderSpanCompiler().compile(source)

    assert plan.span_count == 1
    assert plan.change_frames == ()
    assert plan.boundaries == ()
    assert plan.spans[0].opening_internal_boundary_id is None
    assert plan.spans[0].closing_internal_boundary_id is None


def test_asset_exit_creates_span_boundary_and_removal_authority_on_next_span() -> None:
    source = TimedAssetPresencePlan(
        shot_id="SHT-EXIT",
        frames_per_second=24,
        frame_count=144,
        presences=(
            TimedAssetPresence(
                asset_id="CAP-CHR-001",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=95,
                removal=AssetPresenceRemoval.EXIT,
            ),
            TimedAssetPresence(
                asset_id="CAP-LOC-021",
                asset_kind=TimedAssetKind.LOCATION,
                from_frame=0,
                through_frame=143,
            ),
        ),
    )

    plan = GovernedInternalRenderSpanCompiler().compile(source)

    assert plan.change_frames == (96,)
    assert plan.spans[0].active_asset_ids == ("CAP-CHR-001", "CAP-LOC-021")
    assert plan.spans[1].active_asset_ids == ("CAP-LOC-021",)
    assert plan.spans[1].removed_asset_ids == ("CAP-CHR-001",)


def test_simultaneous_asset_changes_share_one_internal_boundary() -> None:
    source = TimedAssetPresencePlan(
        shot_id="SHT-MULTI",
        frames_per_second=24,
        frame_count=144,
        presences=(
            TimedAssetPresence(
                asset_id="CAP-CHR-A",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=95,
                removal=AssetPresenceRemoval.EXIT,
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-B",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.ENTER,
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-C",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.REVEAL,
            ),
        ),
    )

    plan = GovernedInternalRenderSpanCompiler().compile(source)

    assert plan.span_count == 2
    assert len(plan.boundaries) == 1
    assert plan.spans[1].introduced_asset_ids == ("CAP-CHR-B", "CAP-CHR-C")
    assert plan.spans[1].removed_asset_ids == ("CAP-CHR-A",)


def test_internal_span_plan_round_trip_preserves_identity_and_fingerprint() -> None:
    original = GovernedInternalRenderSpanCompiler().compile(_ros_plan())
    payload = original.to_dict()

    restored = GovernedInternalRenderSpanPlan.from_dict(payload)

    assert restored == original
    assert restored.plan_id == original.plan_id
    assert restored.fingerprint == original.fingerprint


def test_internal_span_plan_detects_boundary_tampering() -> None:
    payload = GovernedInternalRenderSpanCompiler().compile(_ros_plan()).to_dict()
    tampered = deepcopy(payload)
    boundaries = tampered["boundaries"]
    assert isinstance(boundaries, list)
    boundary = boundaries[0]
    assert isinstance(boundary, dict)
    boundary["source_global_frame_index"] = 94

    with pytest.raises(GovernedInternalRenderSpanError):
        GovernedInternalRenderSpanPlan.from_dict(tampered)


def test_internal_span_plan_detects_derived_duration_tampering() -> None:
    payload = GovernedInternalRenderSpanCompiler().compile(_ros_plan()).to_dict()
    tampered = deepcopy(payload)
    spans = tampered["spans"]
    assert isinstance(spans, list)
    span = spans[0]
    assert isinstance(span, dict)
    span["duration_seconds"] = 5.0

    with pytest.raises(GovernedInternalRenderSpanError, match="duration_seconds"):
        GovernedInternalRenderSpanPlan.from_dict(tampered)


def test_internal_span_plan_fails_if_timed_presence_source_changes() -> None:
    source = _ros_plan()
    plan = GovernedInternalRenderSpanCompiler().compile(source)
    changed = TimedAssetPresencePlan(
        shot_id=source.shot_id,
        frames_per_second=source.frames_per_second,
        frame_count=source.frame_count,
        presences=tuple(
            presence
            if presence.asset_id != "CAP-CHR-004"
            else TimedAssetPresence(
                asset_id=presence.asset_id,
                asset_kind=presence.asset_kind,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.REVEAL,
                canonical_reference_ids=presence.canonical_reference_ids,
            )
            for presence in source.presences
        ),
    )

    with pytest.raises(GovernedInternalRenderSpanError, match="identity changed"):
        plan.require_source(changed)


def test_execution_compiler_derives_internal_spans_from_timed_presence() -> None:
    source = _ros_plan()

    payload = ProductionPackageCompilerService._internal_render_spans(source.to_dict())

    assert payload is not None
    assert payload["span_count"] == 2
    assert payload["change_frames"] == [96]
    assert payload["source_timed_asset_presence"]["plan_id"] == source.plan_id


def test_compiled_production_package_carries_internal_span_authority() -> None:
    source = _ros_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(source).to_dict()

    payload = _compiled_package(source.to_dict(), spans).to_dict()

    assert payload["timed_asset_presence"] == source.to_dict()
    assert payload["internal_render_spans"] == spans


def test_provider_boundary_fails_closed_after_successful_multi_span_compilation() -> None:
    source = _ros_plan()
    spans = GovernedInternalRenderSpanCompiler().compile(source).to_dict()

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match="current provider execution is still monolithic",
    ):
        LocalProductionPackageCompilationService._comfyui_payload(
            _compiled_package(source.to_dict(), spans)
        )


def test_single_internal_span_can_pass_current_monolithic_provider_boundary() -> None:
    source = TimedAssetPresencePlan(
        shot_id="EP-001-SCN-001-SHT-002",
        frames_per_second=24,
        frame_count=144,
        presences=(
            TimedAssetPresence(
                asset_id="CAP-CHR-001",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
            ),
        ),
    )
    spans = GovernedInternalRenderSpanCompiler().compile(source).to_dict()

    payload = LocalProductionPackageCompilationService._comfyui_payload(
        _compiled_package(source.to_dict(), spans)
    )

    assert payload["timed_asset_presence"] == source.to_dict()
    assert payload["internal_render_spans"] == spans
