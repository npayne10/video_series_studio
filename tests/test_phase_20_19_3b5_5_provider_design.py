"""Phase B.5.5 provider suggestions remain untrusted until human decisions."""

import pytest
from pydantic import ValidationError

from vscs.application.caps.provider_design_expansion import (
    DesignExpansionResponse,
    ProposedDesignField,
    validate_design_expansion,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory


def _spec():
    return CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering control room",
        canonical_attributes={"architecture": "Vessel control room with a console"},
        master_prompt="Reference proposal",
    )


def test_missing_category_details_are_advisory_only():
    original = _spec()
    proposals = DesignExpansionResponse(
        fields=(
            ProposedDesignField(
                field="layout",
                proposed_value="Console against an interior bulkhead",
                rationale="Plausible proposed arrangement, not a story fact",
            ),
            ProposedDesignField(
                field="lighting",
                proposed_value="Recessed indirect light",
                rationale="Production design suggestion",
            ),
        )
    )
    validated = validate_design_expansion(original, proposals)
    assert set(validated) == {"layout", "lighting"}
    assert original.canonical_attributes == {"architecture": "Vessel control room with a console"}


@pytest.mark.parametrize("field", ["architecture", "not_a_location_field"])
def test_provider_cannot_overwrite_canon_or_add_unsupported_keys(field):
    suggestion = DesignExpansionResponse(
        fields=(ProposedDesignField(field=field, proposed_value="Change", rationale="Suggestion"),)
    )
    with pytest.raises(ValueError, match=r"unsupported|already-defined"):
        validate_design_expansion(_spec(), suggestion)


def test_provider_cannot_return_duplicate_field():
    field = ProposedDesignField(field="layout", proposed_value="Console", rationale="Choice")
    with pytest.raises(ValueError, match="duplicate"):
        validate_design_expansion(_spec(), DesignExpansionResponse(fields=(field, field)))


def test_empty_proposal_or_rationale_is_rejected():
    with pytest.raises(ValueError, match="rationale"):
        validate_design_expansion(
            _spec(),
            DesignExpansionResponse(
                fields=(ProposedDesignField(field="layout", proposed_value="Desk", rationale=""),)
            ),
        )


def test_strict_response_rejects_unknown_properties():
    with pytest.raises(ValidationError):
        DesignExpansionResponse.model_validate({"fields": [], "approved": True})
