"""Phase 20.19.3B.5.2 — category-specific completeness must not imply canon."""

import pytest

from vscs.application.caps.completeness import (
    REQUIRED_FIELDS,
    assess_completeness,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory


def _spec(category, attributes, origin="story_intelligence_proposal"):
    return CAPStructuredSpecification(
        asset_id="CAP-TEST-001",
        category=category,
        design_intent="Reference identity",
        canonical_attributes=attributes,
        master_prompt="Photorealistic reference",
        continuity_rules=("Keep visible identity consistent",),
        origin=origin,
    )


@pytest.mark.parametrize("category", tuple(REQUIRED_FIELDS))
def test_each_category_reports_missing_detail_without_inventing_it(category):
    first_key = REQUIRED_FIELDS[category][0]
    spec = _spec(category, {first_key: "Known description"})
    assessment = assess_completeness(spec)
    assert assessment.missing == REQUIRED_FIELDS[category][1:]
    assert first_key in assessment.unverified
    assert not assessment.ready_for_image_review


def test_fully_populated_story_proposal_is_still_unverified():
    fields = {key: "Proposed detail" for key in REQUIRED_FIELDS[AssetCategory.LOCATION]}
    result = assess_completeness(_spec(AssetCategory.LOCATION, fields))
    assert not result.missing
    assert result.unverified
    assert not result.ready_for_image_review


def test_reviewed_document_does_not_establish_claim_level_source_authority():
    fields = {key: "Reviewed detail" for key in REQUIRED_FIELDS[AssetCategory.PROP]}
    spec = _spec(AssetCategory.PROP, fields, origin="docx_import_reviewed")
    assert not assess_completeness(spec).ready_for_image_review
    assert assess_completeness(spec).unverified
    no_rules = spec.model_copy(update={"continuity_rules": ()})
    assert not assess_completeness(no_rules).ready_for_image_review
