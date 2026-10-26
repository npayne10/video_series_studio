"""Evidence classification and prompt constraints for CAP detail expansion."""

from vscs.application.caps.detail_expansion import (
    DetailAuthority,
    build_review_prompt,
    expand_details,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps.generation import ExtractedCanonicalFact, GeneratedCAPDraft


def _spec():
    return CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering control room",
        canonical_attributes={"layout": "Fixed console", "materials": "brushed alloy"},
        master_prompt="Reference",
    )


def test_evidence_candidate_requires_verbatim_context_and_matching_claim():
    draft = GeneratedCAPDraft(
        title="Engineering control room",
        canonical_description="Fixed console",
        canonical_facts=(
            ExtractedCanonicalFact(
                fact="Fixed console", evidence="The console is fixed.", confidence=0.9
            ),
        ),
    )
    result = expand_details(_spec(), draft, "The console is fixed.")
    assert result.candidates[0].authority is DetailAuthority.STORY_CANDIDATE
    assert result.candidates[1].authority is DetailAuthority.DESIGN_PROPOSAL
    assert "scale" in result.missing
    assert "lighting" in result.missing


def test_unsourced_model_fact_is_not_authorized_as_canon():
    draft = GeneratedCAPDraft(
        title="Room",
        canonical_description="Fixed console",
        canonical_facts=(
            ExtractedCanonicalFact(
                fact="Fixed console", evidence="Invented evidence", confidence=1.0
            ),
        ),
    )
    result = expand_details(_spec(), draft, "A quiet vessel.")
    assert result.candidates[0].authority is DetailAuthority.DESIGN_PROPOSAL


def test_review_prompt_rejects_unspecified_or_changed_values():
    spec = _spec()
    text = build_review_prompt(spec, {"layout": "Fixed console"})
    assert "layout: Fixed console" in text
    for values in ({}, {"lighting": "bright"}, {"layout": "Moved console"}):
        try:
            build_review_prompt(spec, values)
        except ValueError:
            pass
        else:
            raise AssertionError("Unreviewed details must be rejected")
