"""Provider-backed advisory design expansion; no canon promotion or project writes."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from vscs.application.caps.completeness import REQUIRED_FIELDS
from vscs.application.caps.structured_specification import CAPStructuredSpecification


class ProposedDesignField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    proposed_value: str
    rationale: str


class DesignExpansionResponse(BaseModel):
    """Strict wire contract: a list, not unconstrained keyed JSON."""

    model_config = ConfigDict(extra="forbid")
    fields: tuple[ProposedDesignField, ...]


def validate_design_expansion(
    spec: CAPStructuredSpecification, response: DesignExpansionResponse
) -> dict[str, ProposedDesignField]:
    """Accept only unique, missing category keys with nonempty proposed values."""
    required = set(REQUIRED_FIELDS.get(spec.category, ("identity",)))
    missing = required - set(spec.canonical_attributes)
    result: dict[str, ProposedDesignField] = {}
    for item in response.fields:
        if item.field not in missing or item.field in result:
            raise ValueError("Provider returned duplicate, unsupported, or already-defined field")
        if not item.proposed_value.strip() or not item.rationale.strip():
            raise ValueError("Provider must provide a proposed design and rationale")
        result[item.field] = item
    return result


@runtime_checkable
class CAPDesignExpansionProvider(Protocol):
    """Optional capability; ordinary CAP providers need not implement it."""

    def expand_cap_design(
        self, spec: CAPStructuredSpecification, story_context: str
    ) -> DesignExpansionResponse: ...


def validate_scoped_field_regeneration(
    spec: CAPStructuredSpecification,
    field: str,
    response: DesignExpansionResponse,
) -> ProposedDesignField:
    """Check exactly the selected field, whether required or optional.

    The governed application service separately verifies that the original
    stored review decision for this field was explicitly Defer or Reject.
    """
    if not field or field in spec.canonical_attributes:
        raise ValueError("Scoped target field is invalid or already accepted")
    if len(response.fields) != 1 or response.fields[0].field != field:
        raise ValueError("Provider must return only the requested Draft field")
    result = response.fields[0]
    if not result.proposed_value.strip() or not result.rationale.strip():
        raise ValueError("Scoped field requires a proposed value and rationale")
    return result


@runtime_checkable
class CAPSingleFieldRegenerationProvider(Protocol):
    """Provider must return only the explicitly selected missing Draft field."""

    def regenerate_draft_cap_field(
        self,
        spec: CAPStructuredSpecification,
        field: str,
        story_context: str,
        original_proposal: str,
    ) -> DesignExpansionResponse: ...
