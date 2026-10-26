"""Governed Story-to-CAP proposal tests."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.story_specification import StoryCAPSpecificationService
from vscs.domain.assets.models import AssetCategory


@pytest.mark.parametrize(
    ("category", "key"),
    [
        (AssetCategory.CHARACTER, "anatomy"),
        (AssetCategory.LOCATION, "architecture"),
        (AssetCategory.SHIP, "silhouette"),
        (AssetCategory.PROP, "geometry"),
        (AssetCategory.ENVIRONMENT, "geography"),
    ],
)
def test_generates_category_specific_review_only_proposal(category, key):
    generator = Mock()
    generator.assets.get.return_value = SimpleNamespace(
        asset_id="CAP-TEST-001", name="Test Asset", category=category
    )
    generator.generate_draft.return_value = SimpleNamespace(
        visual_identity="Fixed canonical silhouette",
        canonical_description="Controlled story asset",
        continuity_rules=("Preserve dimensions",),
    )
    specs = Mock()
    service = StoryCAPSpecificationService(generator, specs)
    proposal = service.propose("CAP-TEST-001", "Approved story evidence")
    assert key in proposal.specification.canonical_attributes
    assert proposal.specification.origin == "story_intelligence_proposal"
    assert "physically plausible" in proposal.specification.master_prompt
    specs.save_draft.assert_not_called()


def test_empty_context_does_not_call_provider():
    generator = Mock()
    service = StoryCAPSpecificationService(generator, Mock())
    with pytest.raises(ValueError, match="Story context"):
        service.propose("CAP-LOC-001", "")
    generator.generate_draft.assert_not_called()


def test_save_draft_rejects_existing_specification():
    specs = Mock()
    specs.get.return_value = object()
    generator = Mock()
    service = StoryCAPSpecificationService(generator, specs)
    proposal = SimpleNamespace(origin="story_intelligence_proposal", asset_id="CAP-LOC-001")
    with pytest.raises(ValueError, match="revision review"):
        service.save_reviewed(proposal)
    specs.save_draft.assert_not_called()
