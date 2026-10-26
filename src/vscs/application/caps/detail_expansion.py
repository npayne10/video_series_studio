"""Reviewable category-specific CAP details; never promotes model claims into Story Canon."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vscs.application.caps.completeness import REQUIRED_FIELDS
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.caps.generation import GeneratedCAPDraft


class DetailAuthority(StrEnum):
    """Evidence classification for proposed physical details."""

    STORY_CANDIDATE = "story_candidate_unverified"
    DESIGN_PROPOSAL = "design_proposal"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class CanonicalDetailCandidate:
    """Source transparency for one suggested field, before human review."""

    field: str
    value: str
    authority: DetailAuthority
    evidence: str = ""


@dataclass(frozen=True)
class CanonicalDetailExpansion:
    """All category fields, including explicitly unresolved missing attributes."""

    candidates: tuple[CanonicalDetailCandidate, ...]
    missing: tuple[str, ...]


def expand_details(
    specification: CAPStructuredSpecification,
    generated: GeneratedCAPDraft,
    story_context: str,
) -> CanonicalDetailExpansion:
    """Classify only supplied model facts and suggestions; do not invent dimensions.

    A fact is a Story candidate only if its evidence appears verbatim in the
    supplied context. It still requires operator verification against real canon.
    """
    fields = REQUIRED_FIELDS.get(specification.category, ("identity",))
    candidates: list[CanonicalDetailCandidate] = []
    for field in fields:
        current = specification.canonical_attributes.get(field, "").strip()
        if not current:
            candidates.append(CanonicalDetailCandidate(field, "", DetailAuthority.UNRESOLVED))
            continue
        evidence = next(
            (
                fact.evidence
                for fact in generated.canonical_facts
                if fact.evidence.strip()
                and fact.evidence.strip() in story_context
                and (fact.fact.strip() in current or current in fact.fact.strip())
            ),
            "",
        )
        authority = (
            DetailAuthority.STORY_CANDIDATE if evidence else DetailAuthority.DESIGN_PROPOSAL
        )
        candidates.append(CanonicalDetailCandidate(field, current, authority, evidence))
    return CanonicalDetailExpansion(
        tuple(candidates),
        tuple(item.field for item in candidates if item.authority is DetailAuthority.UNRESOLVED),
    )


def build_review_prompt(
    specification: CAPStructuredSpecification,
    accepted: dict[str, str],
) -> str:
    """Make a repeatable identity prompt from human-reviewed details only."""
    if not accepted:
        raise ValueError("No reviewed detail fields supplied")
    if not set(accepted).issubset(specification.canonical_attributes):
        raise ValueError("Reviewed fields must exist in the current CAP")
    if any(specification.canonical_attributes[key] != value for key, value in accepted.items()):
        raise ValueError("Reviewed detail values differ from current CAP")
    details = "; ".join(f"{key}: {accepted[key]}" for key in sorted(accepted))
    return (
        f"Canonical {specification.category.value} reference. "
        f"Design intent: {specification.design_intent}. "
        f"Reviewed fixed details: {details}. "
        "Physically plausible photorealistic reference; keep fixed attributes consistent."
    )
