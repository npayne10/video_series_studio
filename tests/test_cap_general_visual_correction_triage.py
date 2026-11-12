"""F5.4.2: generalized Candidate correction triage remains non-authoritative."""

from types import SimpleNamespace

import pytest

from vscs.application.caps.general_visual_correction_triage import candidate_visual_triage
from vscs.application.caps.geometry_correction_policy import (
    GeometryCorrectionError,
    GeometryDefect,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualityResult


def _report(with_semantic=True):
    snapshot = SimpleNamespace(
        asset_id="STORY-PRO-TEST",
        reference_id=4,
        image_sha256="a" * 64,
        reference_role="supplementary",
        reference_status="candidate",
        accepted_fields=(
            ("components", "Three round buttons and one recessed rotary dial"),
            ("geometry", "Console stands beside a separate workstation"),
        ),
    )
    technical = SimpleNamespace(decision=SimpleNamespace(value="review"))
    semantic = (
        SimpleNamespace(
            decision=SimpleNamespace(value="regenerate"),
            violations=("The rotary dial is raised above the shelf.",),
        )
        if with_semantic
        else None
    )
    return CandidateQualityResult(
        snapshot=snapshot,
        technical=technical,
        semantic=semantic,
        recommendations=(),
    )


def test_all_reviewed_fields_are_unverified_even_with_semantic_report():
    result = candidate_visual_triage(_report())
    assert result.semantic_available
    assert result.quality_decision == "REGENERATE_RECOMMENDED"
    assert result.unresolved_mandatory_checks == 2
    assert all(c.status == "REQUIRES_HUMAN_VERIFICATION" for c in result.mandatory_checks)
    assert "raised above" in result.advisory_violations[0]
    assert not result.gpu_execution_authorized
    assert not result.canon_approval_allowed
    assert not result.cap_registration_allowed
    assert not result.governed_attempt_allowed


def test_no_semantic_review_cannot_become_implicit_pass():
    result = candidate_visual_triage(_report(with_semantic=False))
    assert not result.semantic_available
    assert result.unresolved_mandatory_checks == 2
    assert not result.advisory_violations
    assert "NOT AUTOMATICALLY PASSED" in result.describe()


def test_operator_classification_routes_missing_component_to_rebuild():
    result = candidate_visual_triage(
        _report(),
        selected_field="components",
        selected_defect=GeometryDefect.MISSING_COMPONENT,
        observed_failure="A rotary control is missing inside the reviewed opening.",
    )
    assert result.stages == ("reconstruct_component", "verify_design")
    assert result.selected_field == "components"
    assert "reconstruct_component -> verify_design" in result.describe()
    assert not result.gpu_execution_authorized


@pytest.mark.parametrize("kind", list(GeometryDefect))
def test_all_general_defect_types_have_bounded_correction_route(kind):
    result = candidate_visual_triage(
        _report(),
        selected_field="geometry",
        selected_defect=kind,
        observed_failure="A specific visible geometry problem requires review.",
    )
    assert result.stages[-1] == "verify_design"


def test_unreviewed_field_and_short_failure_fail_closed():
    with pytest.raises(GeometryCorrectionError, match="reviewed CAP field"):
        candidate_visual_triage(
            _report(),
            selected_field="invented",
            selected_defect=GeometryDefect.MISSING_COMPONENT,
            observed_failure="One reviewed component is absent.",
        )
    with pytest.raises(GeometryCorrectionError, match="specific"):
        candidate_visual_triage(
            _report(),
            selected_field="components",
            selected_defect=GeometryDefect.MISSING_COMPONENT,
            observed_failure="bad",
        )


def test_unbound_freeform_reason_is_refused():
    with pytest.raises(GeometryCorrectionError, match="Unbound"):
        candidate_visual_triage(_report(), observed_failure="A feature is wrong")


def test_non_candidate_or_empty_review_fails_closed():
    bad = _report()
    bad.snapshot.reference_status = "approved"
    with pytest.raises(GeometryCorrectionError, match="identity"):
        candidate_visual_triage(bad)
    bad = _report()
    bad.snapshot.accepted_fields = ()
    with pytest.raises(GeometryCorrectionError, match="no reviewed"):
        candidate_visual_triage(bad)
