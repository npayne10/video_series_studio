"""Verified governed evidence can be adapted without approving Draft bindings."""

import pytest

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.governed_planning_evidence import (
    GovernedShotEvidence,
    verified_shots_to_spatial_sources,
)


def _evidence(status: str = "ready") -> GovernedShotEvidence:
    return GovernedShotEvidence(
        story_id="STORY-001",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        text_fields=(("required_action", "Diagnostic Console inside Engineering Control Room."),),
        bound_asset_ids=("CAP-LOC-001", "CAP-PRP-001"),
        contract_hashes=("a" * 64, "b" * 64, "c" * 64),
        binding_statuses=(status,),
    )


def test_verified_evidence_can_be_adapted_with_field_provenance():
    sources = verified_shots_to_spatial_sources((_evidence(),), selected_story_id="STORY-001")
    assert sources[0].shot_id == "SHT-001"
    assert sources[0].text.startswith("required_action:")
    assert sources[0].bound_asset_ids == ("CAP-LOC-001", "CAP-PRP-001")


def test_draft_binding_is_not_forwarded():
    with pytest.raises(ShotTextAuthorityError, match="Unapproved"):
        verified_shots_to_spatial_sources((_evidence("draft"),), selected_story_id="STORY-001")


def test_other_story_is_not_forwarded():
    with pytest.raises(ShotTextAuthorityError, match="Cross-Story"):
        verified_shots_to_spatial_sources((_evidence(),), selected_story_id="STORY-OTHER")
