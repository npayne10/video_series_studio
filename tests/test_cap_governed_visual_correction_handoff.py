"""F5.4.2 C1: correction handoff must never execute or promote evidence."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from vscs.application.caps.general_visual_correction_triage import candidate_visual_triage
from vscs.application.caps.geometry_correction_policy import (
    GeometryCorrectionError,
    GeometryDefect,
)
from vscs.application.caps.governed_visual_correction_handoff import (
    prepare_governed_correction_proposal,
)
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualityResult

SOURCE_SHA = "a" * 64


def _review():
    snapshot = SimpleNamespace(
        asset_id="STORY-PRO-TEST",
        reference_id=4,
        image_sha256=SOURCE_SHA,
        reference_role="supplementary",
        reference_status="candidate",
        accepted_fields=(
            ("components", "Three buttons with one recessed rotary dial"),
            ("geometry", "Distinct workstation beside console"),
        ),
    )
    report = CandidateQualityResult(
        snapshot=snapshot,
        technical=SimpleNamespace(decision=SimpleNamespace(value="review")),
        semantic=SimpleNamespace(
            decision=SimpleNamespace(value="regenerate"),
            violations=("The rotary control seems raised.",),
        ),
        recommendations=(),
    )
    triage = candidate_visual_triage(report)
    failed = propose_spatial_evidence(
        triage,
        field="components",
        status=VisualEvidenceStatus.FAILED,
        observation="The recessed rotary control is missing from the visual Candidate.",
        defect=GeometryDefect.MISSING_COMPONENT,
        region=NormalizedRegion(0.1, 0.2, 0.3, 0.4),
        expected_source_sha256=SOURCE_SHA,
    )
    return propose_spatial_evidence(
        triage,
        previous=failed,
        field="geometry",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="The console and workstation remain physically distinct.",
    )


def _propose(review=None):
    return prepare_governed_correction_proposal(
        _review() if review is None else review,
        target_field="components",
        expected_source_sha256=SOURCE_SHA,
        reviewer_confirmed_roi=True,
    )


def test_full_field_review_produces_immutable_non_executable_handoff():
    proposal = _propose()
    proposal.verify_seal()
    assert proposal.target_field == "components"
    assert proposal.stages == ("reconstruct_component", "verify_design")
    assert proposal.reviewed_roi == NormalizedRegion(0.1, 0.2, 0.3, 0.4)
    assert len(proposal.proposal_sha256) == 64
    assert not proposal.can_generate
    assert not proposal.mask_verified
    assert not proposal.provider_mask_capability_verified
    assert not proposal.gpu_execution_authorized
    assert not proposal.governed_attempt_allowed
    assert not proposal.candidate_registration_allowed
    assert not proposal.cap_registration_allowed
    assert not proposal.canon_approval_allowed
    assert "NOT a mask" in proposal.describe()


def test_explicit_roi_confirmation_and_source_hash_required():
    with pytest.raises(GeometryCorrectionError, match="ROI review"):
        prepare_governed_correction_proposal(
            _review(),
            target_field="components",
            expected_source_sha256=SOURCE_SHA,
            reviewer_confirmed_roi=False,
        )
    with pytest.raises(GeometryCorrectionError, match="source identity"):
        prepare_governed_correction_proposal(
            _review(),
            target_field="components",
            expected_source_sha256="b" * 64,
            reviewer_confirmed_roi=True,
        )


def test_unknown_or_second_failed_field_blocks_handoff():
    review = _review()
    unknown = propose_spatial_evidence(
        candidate_visual_triage(
            CandidateQualityResult(
                snapshot=SimpleNamespace(
                    asset_id=review.asset_id,
                    reference_id=review.reference_id,
                    image_sha256=review.source_sha256,
                    reference_role="supplementary",
                    reference_status="candidate",
                    accepted_fields=tuple(
                        (f.field, f.requirement) for f in review.reviewed_fields
                    ),
                ),
                technical=SimpleNamespace(decision=SimpleNamespace(value="review")),
                semantic=None,
                recommendations=(),
            )
        ),
        field="components",
        status=VisualEvidenceStatus.FAILED,
        observation="The recessed rotary control is missing from the image.",
        defect=GeometryDefect.MISSING_COMPONENT,
        region=NormalizedRegion(0.1, 0.2, 0.3, 0.4),
    )
    with pytest.raises(GeometryCorrectionError, match="All accepted"):
        _propose(unknown)
    fields = list(review.reviewed_fields)
    fields[1] = replace(
        fields[1],
        status=VisualEvidenceStatus.FAILED,
        defect=GeometryDefect.MERGED_OBJECTS,
        correction_stages=("establish_geometry", "verify_design"),
    )
    with pytest.raises(GeometryCorrectionError, match="exactly one"):
        _propose(replace(review, reviewed_fields=tuple(fields)))


def test_region_absence_or_tampered_stages_blocks():
    review = _review()
    fields = list(review.reviewed_fields)
    fields[0] = replace(fields[0], proposed_region=None)
    with pytest.raises(GeometryCorrectionError, match="target evidence"):
        _propose(replace(review, reviewed_fields=tuple(fields)))
    fields[0] = replace(
        review.reviewed_fields[0], correction_stages=("verify_design",)
    )
    with pytest.raises(GeometryCorrectionError, match="target evidence"):
        _propose(replace(review, reviewed_fields=tuple(fields)))


def test_post_handoff_seal_and_authority_tampering_blocked():
    proposal = _propose()
    with pytest.raises(GeometryCorrectionError, match="seal"):
        replace(proposal, observed_failure="A different unreviewed claim").verify_seal()
    with pytest.raises(GeometryCorrectionError, match="authority"):
        replace(proposal, gpu_execution_authorized=True).verify_seal()
    with pytest.raises(GeometryCorrectionError, match="authority"):
        replace(proposal, governed_attempt_allowed=True).verify_seal()
    with pytest.raises(GeometryCorrectionError, match="stages"):
        replace(proposal, stages=("verify_design",)).verify_seal()


def test_upstream_review_cannot_grant_execution_authority():
    with pytest.raises(GeometryCorrectionError, match="production authority"):
        _propose(replace(_review(), gpu_execution_authorized=True))
    with pytest.raises(GeometryCorrectionError, match="production authority"):
        _propose(replace(_review(), governed_attempt_allowed=True))
