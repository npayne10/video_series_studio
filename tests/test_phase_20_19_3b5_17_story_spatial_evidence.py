"""B.5.17 only extracts explicit approved-description ID evidence."""

from vscs.application.caps.story_spatial_evidence import (
    extract_explicit_story_relationships,
    plan_story_spatial_evidence,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory


def _parent():
    return CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Room",
        canonical_attributes={"architecture": "Room"},
        master_prompt="Draft only",
    )


def test_exact_story_relationship_has_traceable_excerpt():
    description = "The text says CAP-PRP-001 is located in CAP-LOC-001."
    result = extract_explicit_story_relationships(
        "STORY-001", description, ("CAP-LOC-001", "CAP-PRP-001")
    )
    assert len(result) == 1
    assert result[0].excerpt == "CAP-PRP-001 is located in CAP-LOC-001"
    assert description[result[0].start_offset :].startswith(result[0].excerpt)


def test_nonregistered_ids_and_ordinary_narrative_do_not_create_evidence():
    description = "Console is in the room. CAP-PRP-999 inside CAP-LOC-001."
    assert not extract_explicit_story_relationships(
        "STORY-001", description, ("CAP-LOC-001", "CAP-PRP-001")
    )


def test_coordinated_plan_reports_unresolved_geometry_without_inventing_it():
    plan = plan_story_spatial_evidence(
        "STORY-001",
        "CAP-PRP-001 inside CAP-LOC-001.",
        _parent(),
        ("CAP-PRP-001", "CAP-LOC-001"),
        (),
    )
    assert len(plan.evidence) == 1
    assert plan.missing_geometry == ("CAP-LOC-001", "CAP-PRP-001")
    assert plan.unresolved == ()


def test_empty_evidence_does_not_claim_new_relationships():
    plan = plan_story_spatial_evidence(
        "STORY-001",
        "A diagnostic console stands nearby.",
        _parent(),
        ("CAP-LOC-001", "CAP-PRP-001"),
        ()
    )
    assert not plan.evidence
    assert plan.unresolved
