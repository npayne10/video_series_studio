from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.production_execution import (
    CanonicalInjectionAssetResolutionError,
    CanonicalInjectionAssetResolver,
    IntroductionInjectionRegionCompiler,
    IntroductionInjectionRegionError,
    IntroductionInjectionSide,
    IntroductionKeyframeRequirement,
)
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
                asset_id="CAP-CHR-005",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.ENTER,
                canonical_reference_ids=("REF-ROS-PRIMARY", "REF-ROS-PROFILE"),
            ),
        ),
    )


def _requirement() -> IntroductionKeyframeRequirement:
    return IntroductionKeyframeRequirement(
        shot_id="EP-001-SCN-001-SHT-002",
        boundary_id="GISB-ROS-ENTER",
        source_span_id="GIRS-SPAN-001",
        target_span_id="GIRS-SPAN-002",
        source_global_frame_index=95,
        target_global_frame_index=96,
        target_through_frame=143,
        active_asset_ids=("CAP-CHR-001", "CAP-CHR-003", "CAP-CHR-005"),
        active_reference_ids=(
            "REF-JAMES",
            "REF-SANDRA",
            "REF-ROS-PRIMARY",
            "REF-ROS-PROFILE",
        ),
        introduced_asset_ids=("CAP-CHR-005",),
        introduced_reference_ids=("REF-ROS-PRIMARY", "REF-ROS-PROFILE"),
        source_span_plan_fingerprint="SPAN-FP",
        source_activation_plan_fingerprint="ACTIVATION-FP",
    )


def _reference_plan() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "status": "passed",
        "references": [
            {
                "reference_id": "REF-JAMES",
                "role": "primary_identity",
                "asset_id": "CAP-CHR-001",
                "source_path": "refs/james.png",
                "file_checksum": "SHA-JAMES",
            },
            {
                "reference_id": "REF-SANDRA",
                "role": "primary_identity",
                "asset_id": "CAP-CHR-003",
                "source_path": "refs/sandra.png",
                "file_checksum": "SHA-SANDRA",
            },
            {
                "reference_id": "REF-ROS-PRIMARY",
                "role": "primary_identity",
                "asset_id": "CAP-CHR-005",
                "source_path": "refs/ros-primary.png",
                "file_checksum": "SHA-ROS-PRIMARY",
            },
            {
                "reference_id": "REF-ROS-PROFILE",
                "role": "secondary_identity",
                "asset_id": "CAP-CHR-005",
                "source_path": "refs/ros-profile.png",
                "file_checksum": "SHA-ROS-PROFILE",
            },
        ],
    }


def test_resolver_pins_exact_character_reference_evidence_in_requirement_order() -> None:
    asset = CanonicalInjectionAssetResolver().resolve(
        _requirement(),
        _timed(),
        _reference_plan(),
    )

    assert asset.asset_id == "CAP-CHR-005"
    assert asset.asset_kind == "character"
    assert asset.reference_ids == ("REF-ROS-PRIMARY", "REF-ROS-PROFILE")
    assert asset.reference_paths == ("refs/ros-primary.png", "refs/ros-profile.png")
    assert asset.reference_sha256 == ("sha-ros-primary", "sha-ros-profile")
    assert asset.authority_id.startswith("CIA-")


@pytest.mark.parametrize("status", ["failed", ""])
def test_resolver_requires_explicitly_passed_reference_plan(status: str) -> None:
    reference_plan = _reference_plan()
    reference_plan["status"] = status

    with pytest.raises(
        CanonicalInjectionAssetResolutionError, match="passed governed ReferencePlan"
    ):
        CanonicalInjectionAssetResolver().resolve(
            _requirement(),
            _timed(),
            reference_plan,
        )


def test_resolver_rejects_reference_bound_to_wrong_asset() -> None:
    reference_plan = _reference_plan()
    references = reference_plan["references"]
    assert isinstance(references, list)
    ros = references[2]
    assert isinstance(ros, dict)
    ros["asset_id"] = "CAP-CHR-999"

    with pytest.raises(CanonicalInjectionAssetResolutionError, match="not bound"):
        CanonicalInjectionAssetResolver().resolve(
            _requirement(),
            _timed(),
            reference_plan,
        )


def test_resolver_rejects_reference_not_authorized_by_timed_presence() -> None:
    requirement = replace(
        _requirement(),
        introduced_reference_ids=("REF-ROS-PRIMARY", "REF-NOT-AUTHORIZED"),
        active_reference_ids=(
            "REF-JAMES",
            "REF-SANDRA",
            "REF-ROS-PRIMARY",
            "REF-NOT-AUTHORIZED",
        ),
    )

    with pytest.raises(CanonicalInjectionAssetResolutionError, match="not authorized"):
        CanonicalInjectionAssetResolver().resolve(
            requirement,
            _timed(),
            _reference_plan(),
        )


def test_resolver_rejects_non_enter_character_presence() -> None:
    timed = _timed()
    presences = tuple(
        replace(
            presence,
            introduction=AssetPresenceIntroduction.APPEAR,
        )
        if presence.asset_id == "CAP-CHR-005"
        else presence
        for presence in timed.presences
    )
    changed = TimedAssetPresencePlan(
        shot_id=timed.shot_id,
        frames_per_second=timed.frames_per_second,
        frame_count=timed.frame_count,
        presences=presences,
    )

    with pytest.raises(CanonicalInjectionAssetResolutionError, match="requires ENTER"):
        CanonicalInjectionAssetResolver().resolve(
            _requirement(),
            changed,
            _reference_plan(),
        )


def test_resolver_rejects_multiple_introduced_assets_for_mvp() -> None:
    requirement = replace(
        _requirement(),
        introduced_asset_ids=("CAP-CHR-005", "CAP-CHR-006"),
        active_asset_ids=("CAP-CHR-001", "CAP-CHR-003", "CAP-CHR-005", "CAP-CHR-006"),
    )

    with pytest.raises(CanonicalInjectionAssetResolutionError, match="exactly one"):
        CanonicalInjectionAssetResolver().resolve(
            requirement,
            _timed(),
            _reference_plan(),
        )


@pytest.mark.parametrize(
    ("side", "expected_box", "expected_pixels"),
    [
        (
            IntroductionInjectionSide.LEFT,
            (0.0, 0.08, 0.18, 0.96),
            (0, 58, 230, 691),
        ),
        (
            IntroductionInjectionSide.RIGHT,
            (0.82, 0.08, 1.0, 0.96),
            (1050, 58, 1280, 691),
        ),
    ],
)
def test_region_compiler_creates_edge_only_partial_visibility_authority(
    side: IntroductionInjectionSide,
    expected_box: tuple[float, float, float, float],
    expected_pixels: tuple[int, int, int, int],
) -> None:
    compiler = IntroductionInjectionRegionCompiler()

    region = compiler.compile(width=1280, height=720, side=side)

    assert region.normalized_box == expected_box
    assert region.partial_visibility_required
    assert region.max_subject_scale_ratio == 0.55
    assert compiler.pixel_box(region, width=1280, height=720) == expected_pixels


def test_region_compiler_refuses_auto_side_instead_of_delegating_placement_to_provider() -> None:
    with pytest.raises(IntroductionInjectionRegionError, match="cannot be delegated"):
        IntroductionInjectionRegionCompiler().compile(
            width=1280,
            height=720,
            side=IntroductionInjectionSide.AUTO,
        )


def test_region_compiler_rejects_central_or_oversized_configuration() -> None:
    with pytest.raises(IntroductionInjectionRegionError, match="edge_width_ratio"):
        IntroductionInjectionRegionCompiler(edge_width_ratio=0.30)

    with pytest.raises(IntroductionInjectionRegionError, match="max_subject_scale_ratio"):
        IntroductionInjectionRegionCompiler(max_subject_scale_ratio=0.75)


def test_region_authority_is_deterministic_for_same_dimensions_and_side() -> None:
    compiler = IntroductionInjectionRegionCompiler()

    first = compiler.compile(
        width=1280,
        height=720,
        side=IntroductionInjectionSide.RIGHT,
    )
    second = compiler.compile(
        width=1280,
        height=720,
        side=IntroductionInjectionSide.RIGHT,
    )

    assert second == first
    assert second.region_id == first.region_id
