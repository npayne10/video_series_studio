"""Q3.1.3 proposal-only reference governance regression cases."""

import pytest

from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceCandidate,
    H3ReferenceGovernanceError,
    propose_h3_reference_selection,
)


def test_required_assets_are_never_silently_deferred() -> None:
    candidates = (
        H3ReferenceCandidate("optional-first", "visual_element", False),
        H3ReferenceCandidate("james", "character", True),
        H3ReferenceCandidate("sandra", "character", True),
        H3ReferenceCandidate("ros", "character", True),
    )
    result = propose_h3_reference_selection(candidates, capacity=3)
    assert result.retained_ids == ("james", "sandra", "ros")
    assert result.proposed_deferred_ids == ("optional-first",)
    assert result.requires_operator_review


def test_guide_overlap_is_only_a_review_proposal() -> None:
    items = (
        H3ReferenceCandidate("james", "character", True),
        H3ReferenceCandidate("planet", "visual_element", False, True),
        H3ReferenceCandidate("bridge", "environment", True, True),
    )
    result = propose_h3_reference_selection(items)
    assert result.retained_ids == ("james", "bridge")
    assert result.proposed_deferred_ids == ("planet",)
    assert "operator" in result.decisions[1].reason.lower()
    assert result.fingerprint == propose_h3_reference_selection(items).fingerprint


def test_capacity_fails_closed_without_dropping_required_assets() -> None:
    items = tuple(H3ReferenceCandidate(str(i), "character", True) for i in range(4))
    with pytest.raises(H3ReferenceGovernanceError, match="explicit replanning"):
        propose_h3_reference_selection(items, capacity=3)


def test_duplicate_ids_are_rejected() -> None:
    items = (
        H3ReferenceCandidate("same", "character", True),
        H3ReferenceCandidate("same", "environment", False),
    )
    with pytest.raises(H3ReferenceGovernanceError, match="Duplicate"):
        propose_h3_reference_selection(items)
