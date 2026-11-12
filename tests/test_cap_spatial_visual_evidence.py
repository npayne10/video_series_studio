"""Review-only F5.4.2 Stage B regression boundaries."""

from types import SimpleNamespace

import pytest

from vscs.application.caps.general_visual_correction_triage import (
    candidate_visual_triage,
)
from vscs.application.caps.geometry_correction_policy import (
    GeometryCorrectionError,
    GeometryDefect,
)
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualityResult


def _report():
    snapshot = SimpleNamespace(
        asset_id="STORY-PRO-TEST", reference_id=4, image_sha256="a" * 64,
        reference_role="supplementary", reference_status="candidate",
        accepted_fields=(
            ("components", "Three round buttons and one recessed rotary dial"),
            ("geometry", "Console stands beside a separate workstation"),
        ),
    )
    return CandidateQualityResult(
        snapshot=snapshot,
        technical=SimpleNamespace(decision=SimpleNamespace(value="review")),
        semantic=SimpleNamespace(
            decision=SimpleNamespace(value="regenerate"),
            violations=("The rotary dial is raised above the shelf.",),
        ),
        recommendations=(),
    )


def _triage():
    return candidate_visual_triage(_report())


def test_baseline_keeps_all_accepted_fields_unknown():
    result = propose_spatial_evidence(_triage())
    assert result.outstanding_fields == 2
    assert all(
        c.status is VisualEvidenceStatus.UNKNOWN for c in result.reviewed_fields
    )
    assert not result.gpu_execution_authorized
    assert not result.cap_registration_allowed
    assert not result.canon_approval_allowed
    assert not result.governed_attempt_allowed


def test_failed_field_proposes_roi_without_mask_or_authority():
    region = NormalizedRegion(0.1, 0.2, 0.3, 0.4)
    result = propose_spatial_evidence(
        _triage(),
        field="components",
        status=VisualEvidenceStatus.FAILED,
        observation="The reviewed recessed dial is not visible in this image.",
        defect=GeometryDefect.MISSING_COMPONENT,
        region=region,
        expected_source_sha256="a" * 64,
    )
    first, second = result.reviewed_fields
    assert first.status is VisualEvidenceStatus.FAILED
    assert first.region_ready_for_review
    assert not first.region_reviewer_confirmed
    assert first.correction_stages == ("reconstruct_component", "verify_design")
    assert second.status is VisualEvidenceStatus.UNKNOWN
    assert "ROI IS A PROPOSAL" in result.describe()


def test_operator_verified_field_is_not_automated_semantic_pass():
    result = propose_spatial_evidence(
        _triage(),
        field="geometry",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="I inspected the console and workstation separation.",
    )
    assert result.outstanding_fields == 1
    assert result.reviewed_fields[1].defect is None
    assert not result.cap_registration_allowed


@pytest.mark.parametrize(
    "region",
    [
        (-0.1, 0.1, 0.2, 0.2),
        (0.9, 0.1, 0.2, 0.2),
        (0.1, 0.95, 0.2, 0.1),
        (0.1, 0.1, 0, 0.2),
        (0.1, 0.1, float("nan"), 0.2),
        (0.1, 0.1, float("inf"), 0.2),
        (True, 0.1, 0.2, 0.2),
    ],
)
def test_invalid_rois_fail_closed(region):
    with pytest.raises(GeometryCorrectionError, match="ROI"):
        NormalizedRegion(*region)


def test_source_mismatch_unreviewed_field_and_invalid_states_fail_closed():
    with pytest.raises(GeometryCorrectionError, match="hash mismatch"):
        propose_spatial_evidence(_triage(), expected_source_sha256="b" * 64)
    with pytest.raises(GeometryCorrectionError, match="reviewed CAP"):
        propose_spatial_evidence(_triage(), field="unreviewed")
    with pytest.raises(GeometryCorrectionError, match="status"):
        propose_spatial_evidence(
            _triage(), field="components", status="FAILED"  # type: ignore[arg-type]
        )


def test_no_implicit_pass_from_semantic_prose_and_no_unknown_evidence():
    with pytest.raises(GeometryCorrectionError, match="Unknown field"):
        propose_spatial_evidence(
            _triage(),
            field="components",
            observation="Evaluator thinks the control might be present.",
        )
    with pytest.raises(GeometryCorrectionError, match="requires observed"):
        propose_spatial_evidence(
            _triage(),
            field="components",
            status=VisualEvidenceStatus.FAILED,
            observation="The recessed rotary dial is absent from the candidate.",
        )
    with pytest.raises(GeometryCorrectionError, match="requires operator"):
        propose_spatial_evidence(
            _triage(),
            field="components",
            status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
            observation="not enough",
        )

def test_independent_fields_accumulate_without_semantic_promotion():
    first = propose_spatial_evidence(
        _triage(),
        field="components",
        status=VisualEvidenceStatus.FAILED,
        defect=GeometryDefect.MISSING_COMPONENT,
        observation="The recessed rotary dial is absent from the image.",
    )
    second = propose_spatial_evidence(
        _triage(),
        previous=first,
        field="geometry",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="The workstation appears clearly separated from the console.",
    )
    assert second.outstanding_fields == 0
    assert second.reviewed_fields[0] == first.reviewed_fields[0]
    assert second.reviewed_fields[1].status is VisualEvidenceStatus.VERIFIED_BY_OPERATOR
    assert not second.cap_registration_allowed


def test_previous_review_cannot_cross_source_or_design_revision():
    first = propose_spatial_evidence(_triage())
    altered = _report()
    altered.snapshot.accepted_fields = (("geometry", "Different requirement"),)
    with pytest.raises(GeometryCorrectionError, match="stale or unbound"):
        propose_spatial_evidence(candidate_visual_triage(altered), previous=first)
    altered = _report()
    altered.snapshot.image_sha256 = "b" * 64
    with pytest.raises(GeometryCorrectionError, match="stale or unbound"):
        propose_spatial_evidence(candidate_visual_triage(altered), previous=first)
