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
