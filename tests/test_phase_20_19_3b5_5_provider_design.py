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


def test_b525_terra_design_expansion_corrects_event_and_unsourced_mounting(monkeypatch):
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    provider = object.__new__(OpenAICAPGenerationProvider)
    calls = []

    def parse(*, instructions, input_text, result_type, stage):
        calls.append((instructions, input_text, stage))
        if len(calls) == 1:
            return DesignExpansionResponse(
                fields=(
                    ProposedDesignField(
                        field="lighting",
                        proposed_value="The small indicator pulses once then returns to steady glow.",
                        rationale="Unwanted shot event",
                    ),
                    ProposedDesignField(
                        field="spatial_anchors",
                        proposed_value="A small indicator sits beside the doorway.",
                        rationale="Unsubstantiated placement",
                    ),
                )
            )
        return DesignExpansionResponse(
            fields=(
                ProposedDesignField(
                    field="lighting",
                    proposed_value="Proposed neutral-white recessed fixtures.",
                    rationale="Stable lighting design proposal",
                ),
                ProposedDesignField(
                    field="spatial_anchors",
                    proposed_value="The indicator's mounting remains unresolved.",
                    rationale="No established source anchor",
                ),
            )
        )

    monkeypatch.setattr(provider, "_parse", parse)
    response = provider.expand_cap_design(
        _spec(),
        "The indicator pulses once. The room has a console beside a workstation.",
    )
    assert len(calls) == 2
    assert calls[1][2] == "CAP design detail correction"
    assert "transient_shot_event" in calls[1][1]
    assert "unsupported_indicator_placement" in calls[1][1]
    assert response.fields[0].proposed_value == "Proposed neutral-white recessed fixtures."


def test_b525_clean_design_expansion_never_spends_corrective_call(monkeypatch):
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    provider = object.__new__(OpenAICAPGenerationProvider)
    calls = []

    def parse(*, instructions, input_text, result_type, stage):
        calls.append(stage)
        return DesignExpansionResponse(
            fields=(
                ProposedDesignField(
                    field="lighting",
                    proposed_value="Proposed neutral-white recessed fixtures.",
                    rationale="Physical design choice",
                ),
            )
        )

    monkeypatch.setattr(provider, "_parse", parse)
    provider.expand_cap_design(_spec(), "An empty engineering room.")
    assert calls == ["CAP design detail proposals"]


def test_b525_grounding_failure_after_one_retry_fails_closed(monkeypatch):
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider
    from vscs.infrastructure.ai.provider import AIProviderError

    provider = object.__new__(OpenAICAPGenerationProvider)
    calls = []

    def parse(*, instructions, input_text, result_type, stage):
        calls.append(stage)
        return DesignExpansionResponse(
            fields=(
                ProposedDesignField(
                    field="lighting",
                    proposed_value="Indicator pulses once, then returns to steady.",
                    rationale="Temporary event",
                ),
            )
        )

    monkeypatch.setattr(provider, "_parse", parse)
    with pytest.raises(AIProviderError, match="grounding failed after one correction"):
        provider.expand_cap_design(_spec(), "The indicator pulses once.")
    assert len(calls) == 2
