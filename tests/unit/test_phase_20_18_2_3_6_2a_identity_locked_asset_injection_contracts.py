from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.production_execution import (
    CanonicalInjectionAsset,
    InjectionRegionAuthority,
    IntroductionAssetInjectionError,
    IntroductionInjectionCandidateStatus,
    IntroductionInjectionDecision,
    IntroductionInjectionMode,
    IntroductionInjectionRequest,
    IntroductionInjectionResult,
    IntroductionInjectionReview,
    IntroductionInjectionReviewStore,
    IntroductionInjectionSide,
)


def _asset() -> CanonicalInjectionAsset:
    return CanonicalInjectionAsset(
        asset_id="CAP-CHR-005",
        asset_kind="character",
        reference_ids=("LIVE-SECONDARY_IDENTITY-CAP-CHR-005",),
        reference_paths=(
            "CAP/characters/CAP-CHR-005_Major_Ros_Rohsgard/approved/"
            "CAP-CHR-005 V2.png",
        ),
        reference_sha256=("ABCDEF1234",),
    )


def _region() -> InjectionRegionAuthority:
    return InjectionRegionAuthority(
        side=IntroductionInjectionSide.RIGHT,
        left=0.82,
        top=0.08,
        right=1.0,
        bottom=0.96,
        partial_visibility_required=True,
        max_subject_scale_ratio=0.55,
    )


def _request() -> IntroductionInjectionRequest:
    return IntroductionInjectionRequest(
        shot_id="ep-001-scn-001-sht-002",
        requirement_id="GIKR-ROS-ENTER",
        boundary_id="GISB-ROS-ENTER",
        source_span_id="GIRS-SPAN-001",
        target_span_id="GIRS-SPAN-002",
        source_global_frame_index=95,
        target_global_frame_index=96,
        source_boundary_image_path=(
            ".vscs/automated_introduction_boundaries/"
            "EP-001-SCN-001-SHT-002/GIKR-ROS-ENTER/source-frame-000095.png"
        ),
        source_boundary_image_sha256="SOURCE-SHA",
        canonical_asset=_asset(),
        injection_region=_region(),
        width=1280,
        height=720,
        seed=138,
        timed_asset_presence_fingerprint="TIMED-PRESENCE-FP",
        source_package_fingerprint="PACKAGE-FP",
    )


def _result(request: IntroductionInjectionRequest, *, attempt: int = 1) -> IntroductionInjectionResult:
    return IntroductionInjectionResult(
        request_id=request.request_id,
        requirement_id=request.requirement_id,
        image_path=(
            ".vscs/introduction_injection/"
            f"{request.shot_id}/{request.requirement_id}/{request.request_id}/"
            "frame-000096.png"
        ),
        image_sha256=f"CANDIDATE-SHA-{attempt}",
        canonical_asset_id=request.canonical_asset.authority_id,
        injection_region_id=request.injection_region.region_id,
        provider_name="ComfyUI Identity-Locked Injection",
        model="Qwen Image Edit 2511",
        generated_at=f"2026-09-27T14:4{attempt}:00+02:00",
        attempt_number=attempt,
    )


def test_injection_region_is_normalized_edge_anchored_and_fingerprinted() -> None:
    region = _region()

    assert region.normalized_box == (0.82, 0.08, 1.0, 0.96)
    assert region.partial_visibility_required
    assert region.max_subject_scale_ratio == 0.55
    assert region.region_id.startswith("IIRG-")
    assert InjectionRegionAuthority.from_dict(region.to_dict()) == region


@pytest.mark.parametrize(
    ("side", "left", "right", "message"),
    [
        (IntroductionInjectionSide.LEFT, 0.1, 0.2, "left frame edge"),
        (IntroductionInjectionSide.RIGHT, 0.8, 0.9, "right frame edge"),
    ],
)
def test_injection_region_rejects_unanchored_explicit_edges(
    side: IntroductionInjectionSide,
    left: float,
    right: float,
    message: str,
) -> None:
    with pytest.raises(IntroductionAssetInjectionError, match=message):
        InjectionRegionAuthority(
            side=side,
            left=left,
            top=0.0,
            right=right,
            bottom=1.0,
        )


def test_canonical_asset_requires_aligned_reference_evidence() -> None:
    with pytest.raises(IntroductionAssetInjectionError, match="aligned"):
        CanonicalInjectionAsset(
            asset_id="CAP-CHR-005",
            asset_kind="character",
            reference_ids=("REF-ROS",),
            reference_paths=("ros.png", "other.png"),
            reference_sha256=("abc",),
        )


def test_canonical_asset_round_trip_detects_tampering() -> None:
    asset = _asset()
    raw = asset.to_dict()

    assert CanonicalInjectionAsset.from_dict(raw) == asset

    tampered = dict(raw)
    tampered["asset_id"] = "CAP-CHR-999"
    with pytest.raises(IntroductionAssetInjectionError, match="identity"):
        CanonicalInjectionAsset.from_dict(tampered)


def test_character_enter_request_pins_boundary_identity_region_and_version() -> None:
    request = _request()

    assert request.shot_id == "EP-001-SCN-001-SHT-002"
    assert request.mode is IntroductionInjectionMode.CHARACTER_ENTER
    assert request.injection_version == "3.6.2"
    assert request.source_global_frame_index == 95
    assert request.target_global_frame_index == 96
    assert request.canonical_asset.asset_id == "CAP-CHR-005"
    assert request.injection_region.side is IntroductionInjectionSide.RIGHT
    assert request.request_id.startswith("IIAR-")
    assert IntroductionInjectionRequest.from_dict(request.to_dict()) == request


def test_character_enter_request_requires_character_and_partial_visibility() -> None:
    non_character = replace(_asset(), asset_kind="ship")
    with pytest.raises(IntroductionAssetInjectionError, match="character canonical asset"):
        replace(_request(), canonical_asset=non_character)

    full_visibility = replace(_region(), partial_visibility_required=False)
    with pytest.raises(IntroductionAssetInjectionError, match="partial first-frame visibility"):
        replace(_request(), injection_region=full_visibility)


def test_request_identity_changes_when_seed_or_region_changes() -> None:
    request = _request()

    retry = replace(request, seed=request.seed + 1)
    moved_region = replace(
        request,
        injection_region=replace(request.injection_region, left=0.78),
    )

    assert retry.request_id != request.request_id
    assert moved_region.request_id != request.request_id


def test_injection_result_is_request_scoped_and_tamper_evident() -> None:
    request = _request()
    result = _result(request)

    assert result.request_id == request.request_id
    assert result.attempt_number == 1
    assert result.result_id.startswith("IIAS-")
    assert request.request_id in Path(result.image_path).parts
    assert IntroductionInjectionResult.from_dict(result.to_dict()) == result

    tampered = result.to_dict()
    tampered["attempt_number"] = 2
    with pytest.raises(IntroductionAssetInjectionError, match="identity"):
        IntroductionInjectionResult.from_dict(tampered)


def test_candidate_status_exposes_exact_authority_and_pending_state() -> None:
    request = _request()
    result = _result(request)
    status = IntroductionInjectionCandidateStatus(
        requirement_id=request.requirement_id,
        result_id=result.result_id,
        image_path=result.image_path,
        image_sha256=result.image_sha256,
        canonical_asset=request.canonical_asset,
        injection_region=request.injection_region,
        target_global_frame_index=request.target_global_frame_index,
        attempt_number=result.attempt_number,
    )

    assert status.pending
    assert status.canonical_asset.authority_id == result.canonical_asset_id
    assert status.injection_region.region_id == result.injection_region_id


def test_review_store_is_append_only_and_tracks_rejections(tmp_path: Path) -> None:
    request = _request()
    first_result = _result(request, attempt=1)
    second_request = replace(request, seed=request.seed + 1)
    second_result = _result(second_request, attempt=2)
    store = IntroductionInjectionReviewStore(tmp_path)

    first_review = store.record(
        requirement_id=request.requirement_id,
        result_id=first_result.result_id,
        image_sha256=first_result.image_sha256,
        decision=IntroductionInjectionDecision.REJECTED,
        reviewed_by="Neill Payne",
        notes="Wrong placement.",
        reviewed_at="2026-09-27T14:50:00+02:00",
    )
    second_review = store.record(
        requirement_id=request.requirement_id,
        result_id=second_result.result_id,
        image_sha256=second_result.image_sha256,
        decision=IntroductionInjectionDecision.APPROVED,
        reviewed_by="Neill Payne",
        notes="Identity, region, and scale approved.",
        reviewed_at="2026-09-27T14:55:00+02:00",
    )

    assert first_review.decision is IntroductionInjectionDecision.REJECTED
    assert second_review.decision is IntroductionInjectionDecision.APPROVED
    assert store.rejected_count(request.requirement_id) == 1
    assert store.approved(second_result.result_id, second_result.image_sha256)
    assert not store.approved(first_result.result_id, first_result.image_sha256)

    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert len(raw["reviews"]) == 2
    assert raw["reviews"][0]["review_id"] == first_review.review_id
    assert raw["reviews"][1]["review_id"] == second_review.review_id


def test_review_round_trip_detects_decision_tampering() -> None:
    review = IntroductionInjectionReview(
        requirement_id="GIKR-ROS-ENTER",
        result_id="IIAS-RESULT",
        image_sha256="ABC123",
        decision=IntroductionInjectionDecision.APPROVED,
        reviewed_by="Neill Payne",
        reviewed_at="2026-09-27T15:00:00+02:00",
        notes="Approved.",
    )
    raw = review.to_dict()

    assert IntroductionInjectionReview.from_dict(raw) == review

    tampered = dict(raw)
    tampered["decision"] = IntroductionInjectionDecision.REJECTED.value
    with pytest.raises(IntroductionAssetInjectionError, match="identity"):
        IntroductionInjectionReview.from_dict(tampered)
