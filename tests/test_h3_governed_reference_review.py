"""Q3.1.3.1 read-only governed reference reconciliation."""

from dataclasses import replace

from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceCandidate,
    H3ReferenceGovernanceError,
)

import pytest

from vscs.application.provider_reference_capacity import ProviderReferenceCapacityProjection
from vscs.infrastructure.production_execution.h3_governed_reference_review import (
    review_governed_h3_references,
)


def _projection() -> ProviderReferenceCapacityProjection:
    return ProviderReferenceCapacityProjection(
        provider_id="minimax-h3-ref2va",
        provider_profile_id="test-profile",
        provider_profile_fingerprint="fingerprint",
        model_family="minimax-h3",
        reference_projection_mode="direct_span_scoped_canonical_refs",
        capacity=3,
        required_reference_ids=("james", "sandra"),
        preferred_ready_reference_ids=("bridge", "planet"),
        selected_reference_ids=("james", "sandra", "bridge"),
        deferred_preferred_reference_ids=("planet",),
        indirect_projection=False,
    )


def _candidates() -> tuple[H3ReferenceCandidate, ...]:
    return (
        H3ReferenceCandidate("james", "character", True),
        H3ReferenceCandidate("sandra", "character", True),
        H3ReferenceCandidate("bridge", "environment", False),
        H3ReferenceCandidate("planet", "visual_element", False),
    )


def test_review_is_non_mutating_and_identifies_guide_overlap() -> None:
    projection = _projection()
    before = projection.to_dict()
    review = review_governed_h3_references(
        projection, _candidates(), guide_overlap_ids=frozenset({"bridge", "planet"})
    )
    assert projection.to_dict() == before
    assert review.governed_selected_ids == ("james", "sandra", "bridge")
    assert review.governed_deferred_ids == ("planet",)
    assert review.proposed_changes_to_governed_slots == ("bridge",)
    assert review.requires_operator_review
    assert (
        review.authority_fingerprint
        == review_governed_h3_references(
            projection, _candidates(), guide_overlap_ids=frozenset({"bridge", "planet"})
        ).authority_fingerprint
    )


def test_required_reference_missing_fails_closed() -> None:
    projection = replace(_projection(), selected_reference_ids=("james", "bridge"))
    with pytest.raises(H3ReferenceGovernanceError, match="Required"):
        review_governed_h3_references(projection, _candidates())


def test_stale_projection_order_fails_closed() -> None:
    projection = replace(_projection(), selected_reference_ids=("sandra", "james", "bridge"))
    with pytest.raises(H3ReferenceGovernanceError, match="precedence"):
        review_governed_h3_references(projection, _candidates())


def test_required_flag_mismatch_fails_closed() -> None:
    candidates = list(_candidates())
    candidates[2] = H3ReferenceCandidate("bridge", "environment", True)
    with pytest.raises(H3ReferenceGovernanceError, match="required flags"):
        review_governed_h3_references(_projection(), tuple(candidates))


def test_non_executable_projection_fails_closed() -> None:
    with pytest.raises(H3ReferenceGovernanceError, match="not executable"):
        review_governed_h3_references(
            replace(_projection(), blocked_reason="Requires replanning"), _candidates()
        )
