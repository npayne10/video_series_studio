"""One-field existing Draft CAP OpenAI contract: no implicit retries or edits."""

from unittest.mock import Mock

import pytest

from vscs.application.caps.provider_design_expansion import (
    DesignExpansionResponse,
    ProposedDesignField,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory
from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider
from vscs.infrastructure.ai.provider import AIProviderError


def _spec():
    return CAPStructuredSpecification(
        asset_id="STORY-PRO-TEST",
        category=AssetCategory.PROP,
        design_intent="Diagnostic console",
        canonical_attributes={
            "components": "Blue display",
            "materials": "Graphite coated aluminium",
            "scale": "1.10 metres tall",
        },
        master_prompt="Unapproved Draft",
    )


def _provider(response):
    provider = object.__new__(OpenAICAPGenerationProvider)
    provider._model = "mock"
    provider._parse = Mock(return_value=response)
    return provider


def test_provider_requests_one_field_only_with_immutable_accepted_design():
    response = DesignExpansionResponse(
        fields=(
            ProposedDesignField(
                field="geometry",
                proposed_value="Proposed rectangular console with blue display",
                rationale="Proposed housing design; not established Story fact",
            ),
        )
    )
    provider = _provider(response)
    output = provider.regenerate_draft_cap_field(
        _spec(),
        "geometry",
        "The diagnostic console has a blue display.",
        "The console has a blue display.",
    )
    assert output == response
    provider._parse.assert_called_once()
    kwargs = provider._parse.call_args.kwargs
    assert "TARGET FIELD ONLY: geometry" in kwargs["input_text"]
    assert "Graphite coated aluminium" in kwargs["input_text"]
    assert "no other fields" in kwargs["instructions"]


def test_existing_accepted_field_is_rejected_without_api_request():
    provider = _provider(DesignExpansionResponse(fields=()))
    with pytest.raises(AIProviderError, match="not eligible"):
        provider.regenerate_draft_cap_field(
            _spec(), "materials", "A console.", "Original"
        )
    provider._parse.assert_not_called()


def test_wrong_field_is_rejected_after_exactly_one_request():
    provider = _provider(
        DesignExpansionResponse(
            fields=(
                ProposedDesignField(
                    field="materials",
                    proposed_value="Steel",
                    rationale="Unapproved material",
                ),
            )
        )
    )
    with pytest.raises(ValueError, match="already-defined"):
        provider.regenerate_draft_cap_field(
            _spec(), "geometry", "The diagnostic console has a blue display.", "Original"
        )
    provider._parse.assert_called_once()


def test_empty_or_incomplete_response_does_not_trigger_silent_retry():
    provider = _provider(DesignExpansionResponse(fields=()))
    with pytest.raises(AIProviderError, match="exactly the requested"):
        provider.regenerate_draft_cap_field(
            _spec(), "geometry", "The diagnostic console has a blue display.", "Original"
        )
    provider._parse.assert_called_once()
