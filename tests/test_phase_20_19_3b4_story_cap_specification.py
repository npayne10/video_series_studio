"""Governed Story-to-CAP proposal tests."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.story_specification import StoryCAPSpecificationService
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps.generation import GeneratedCAPDraft


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
    generator.generate_draft.return_value = GeneratedCAPDraft(
        title="Test Asset",
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


def test_b525_other_providers_cannot_cache_ungrounded_design_suggestions():
    from vscs.application.caps.provider_design_expansion import (
        DesignExpansionResponse,
        ProposedDesignField,
    )

    asset = SimpleNamespace(
        asset_id="STORY-LOC-001", name="Engineering control room", category=AssetCategory.LOCATION
    )
    draft = GeneratedCAPDraft(
        title="Engineering control room",
        visual_identity="Diagnostic console beside the workstation.",
        canonical_description="Engineering control room on an unmanned ship.",
    )
    provider = SimpleNamespace(
        expand_cap_design=lambda _spec, _story: DesignExpansionResponse(
            fields=(
                ProposedDesignField(
                    field="lighting",
                    proposed_value="A small indicator pulses once before returning to steady glow.",
                    rationale="Shot event",
                ),
            )
        )
    )
    with pytest.raises(ValueError, match="Design-expansion grounding must be corrected"):
        StoryCAPSpecificationService.proposal_from_draft(
            asset,
            "The indicator pulses once in the approved Shot.",
            draft,
            provider,
        )


def test_b525_other_providers_can_propose_permanent_design_choices():
    from vscs.application.caps.provider_design_expansion import (
        DesignExpansionResponse,
        ProposedDesignField,
    )

    asset = SimpleNamespace(
        asset_id="STORY-LOC-001", name="Engineering control room", category=AssetCategory.LOCATION
    )
    draft = GeneratedCAPDraft(
        title="Engineering control room",
        visual_identity="Diagnostic console beside the workstation.",
        canonical_description="Engineering control room on an unmanned ship.",
    )
    provider = SimpleNamespace(
        expand_cap_design=lambda _spec, _story: DesignExpansionResponse(
            fields=(
                ProposedDesignField(
                    field="lighting",
                    proposed_value="Proposed fixed recessed lighting fixtures.",
                    rationale="Stable design choice, not Story canon",
                ),
            )
        )
    )
    proposal = StoryCAPSpecificationService.proposal_from_draft(
        asset,
        "An engineering control room holds a diagnostic console.",
        draft,
        provider,
    )
    assert proposal.design_suggestions[0].field == "lighting"
    assert proposal.specification.origin == "story_intelligence_proposal"
