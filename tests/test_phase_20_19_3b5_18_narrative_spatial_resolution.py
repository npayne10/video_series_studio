"""Narrative spatial proposals require precise registered names and source evidence."""

from vscs.application.caps.narrative_spatial_resolution import (
    resolve_narrative_spatial_relationships,
)
from vscs.domain.assets.models import Asset


def _asset(asset_id: str, name: str) -> Asset:
    return Asset.model_construct(asset_id=asset_id, name=name)


def test_named_console_is_resolved_with_original_evidence():
    description = "The Diagnostic Console is located in Engineering Control Room."
    result = resolve_narrative_spatial_relationships(
        "STORY-001",
        description,
        (
            _asset("CAP-PRP-001", "Diagnostic Console"),
            _asset("CAP-LOC-001", "Engineering Control Room"),
        ),
    )
    assert len(result.resolved) == 1
    assert result.resolved[0].child_asset_id == "CAP-PRP-001"
    assert result.resolved[0].parent_asset_id == "CAP-LOC-001"
    assert result.resolved[0].excerpt in description
    assert result.ambiguous == ()


def test_ambiguous_duplicate_names_never_resolve():
    result = resolve_narrative_spatial_relationships(
        "STORY-001",
        "Diagnostic Console inside Engineering Control Room.",
        (
            _asset("CAP-PRP-001", "Diagnostic Console"),
            _asset("CAP-PRP-002", "Diagnostic Console"),
            _asset("CAP-LOC-001", "Engineering Control Room"),
        ),
    )
    assert not result.resolved
    assert len(result.ambiguous) == 1


def test_unmentioned_or_implied_relations_are_not_generated():
    result = resolve_narrative_spatial_relationships(
        "STORY-001",
        "The console glowed. The crew entered the room.",
        (
            _asset("CAP-PRP-001", "Diagnostic Console"),
            _asset("CAP-LOC-001", "Engineering Control Room"),
        ),
    )
    assert result.resolved == ()
    assert result.ambiguous == ()
