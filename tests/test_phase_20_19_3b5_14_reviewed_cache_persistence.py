"""Reviewed cross-asset edits survive cache reload without creating a CAP."""

from dataclasses import replace

from vscs.application.caps.proposal_cache import CAPProposalCache
from vscs.application.caps.story_batch import StoryBatchProposal
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)
from vscs.domain.assets.models import AssetCategory


def test_reviewed_relationship_survives_restart_as_unapproved_proposal(tmp_path):
    initial = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering control room",
        canonical_attributes={"architecture": "Vessel interior"},
        master_prompt="Draft-only proposal",
    )
    proposal = StoryCAPProposal(initial, "architecture", ("Unapproved",))
    item = StoryBatchProposal("STORY-001", "fingerprint", "CAP-LOC-001", proposal)
    reviewed = initial.model_copy(
        update={
            "dependency_asset_ids": ("CAP-PRP-001",),
            "dependency_constraints": (
                DependencyConstraint(
                    target_asset_id="CAP-PRP-001",
                    relation=DependencyRelation.CONTAINS,
                    anchor="forward bulkhead",
                    minimum_clearance_mm=900,
                ),
            ),
        }
    )
    reviewed.validate_category_contract()
    item = replace(item, proposal=replace(item.proposal, specification=reviewed))
    CAPProposalCache(tmp_path).save(item, "asset", "provider")
    restored = CAPProposalCache(tmp_path).load(
        "STORY-001", "CAP-LOC-001", "fingerprint", "asset", "provider"
    )
    assert restored is not None
    assert restored.proposal.specification.dependency_constraints == reviewed.dependency_constraints
    assert restored.proposal.specification.dependency_asset_ids == ("CAP-PRP-001",)
    assert not (tmp_path / "production" / "caps" / "CAP-LOC-001.json").exists()
