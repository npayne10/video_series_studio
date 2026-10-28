"""Project-local cached CAP proposals are advisory and fingerprint-scoped."""

from vscs.application.caps.proposal_cache import CAPProposalCache
from vscs.application.caps.story_batch import StoryBatchProposal
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory


def _proposal() -> StoryBatchProposal:
    spec = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering control room",
        canonical_attributes={"architecture": "Interior vessel room"},
        master_prompt="Reference proposal only",
        origin="story_intelligence_proposal",
    )
    proposal = StoryCAPProposal(
        specification=spec,
        suggested_attribute_key="architecture",
        limitations=("Unapproved",),
    )
    return StoryBatchProposal("STORY-001", "story-sha", "CAP-LOC-001", proposal)


def test_cache_survives_reopening_and_preserves_draft(tmp_path):
    item = _proposal()
    CAPProposalCache(tmp_path).save(item, "asset-sha", "provider-sha")
    loaded = CAPProposalCache(tmp_path).load(
        "STORY-001", "CAP-LOC-001", "story-sha", "asset-sha", "provider-sha"
    )
    assert loaded is not None
    assert loaded.proposal.specification == item.proposal.specification
    assert loaded.proposal.specification.origin == "story_intelligence_proposal"


def test_story_asset_or_provider_change_forces_cache_miss(tmp_path):
    item = _proposal()
    cache = CAPProposalCache(tmp_path)
    cache.save(item, "asset-sha", "provider-sha")
    for story, asset, provider in (
        ("changed-story", "asset-sha", "provider-sha"),
        ("story-sha", "changed-asset", "provider-sha"),
        ("story-sha", "asset-sha", "changed-provider"),
    ):
        assert cache.load("STORY-001", "CAP-LOC-001", story, asset, provider) is None


def test_corrupt_cache_is_ignored_without_provider_side_effect(tmp_path):
    cache = CAPProposalCache(tmp_path)
    cache.directory.mkdir(parents=True)
    cache._path("STORY-001", "CAP-LOC-001").write_text("{bad JSON", encoding="utf-8")
    assert cache.load("STORY-001", "CAP-LOC-001", "story", "asset", "provider") is None
