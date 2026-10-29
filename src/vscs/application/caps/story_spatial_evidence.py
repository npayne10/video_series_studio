"""Conservative, project-scoped Story evidence planning without model calls."""

from __future__ import annotations

import re
from dataclasses import dataclass

from vscs.application.caps.structured_specification import CAPStructuredSpecification

_ID = r"[A-Z][A-Z0-9]*-(?:[A-Z0-9]+-)*\d+"
_RELATION = re.compile(
    rf"\b(?P<child>{_ID})\s+(?:is\s+)?(?:located\s+in|inside)\s+(?P<parent>{_ID})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StorySpatialEvidence:
    child_asset_id: str
    parent_asset_id: str
    story_id: str
    excerpt: str
    start_offset: int
    source_kind: str = "approved_story_description_explicit_id_relation"


@dataclass(frozen=True)
class CoordinatedSpatialPlan:
    story_id: str
    parent_asset_id: str
    evidence: tuple[StorySpatialEvidence, ...]
    missing_geometry: tuple[str, ...]
    unresolved: tuple[str, ...]


def extract_explicit_story_relationships(
    story_id: str,
    description: str,
    registered_asset_ids: tuple[str, ...],
) -> tuple[StorySpatialEvidence, ...]:
    """Extract only exact asset-ID statements, never infer relationships from prose."""
    allowed = set(registered_asset_ids)
    found: list[StorySpatialEvidence] = []
    for match in _RELATION.finditer(description):
        child = match.group("child").upper()
        parent = match.group("parent").upper()
        if child not in allowed or parent not in allowed or child == parent:
            continue
        found.append(
            StorySpatialEvidence(
                child, parent, story_id, match.group(0), match.start()
            )
        )
    return tuple(found)


def plan_story_spatial_evidence(
    story_id: str,
    description: str,
    parent: CAPStructuredSpecification,
    registered_asset_ids: tuple[str, ...],
    specifications: tuple[CAPStructuredSpecification, ...],
) -> CoordinatedSpatialPlan:
    """Make a read-only, provenance-bearing plan for the selected parent.

    The caller must authenticate the approved Story and its fingerprint first.
    """
    evidence = tuple(
        item
        for item in extract_explicit_story_relationships(
            story_id, description, registered_asset_ids
        )
        if item.parent_asset_id == parent.asset_id
    )
    known = {spec.asset_id: spec for spec in specifications}
    affected = {item.child_asset_id for item in evidence}
    affected.update(parent.dependency_asset_ids)
    missing: list[str] = []
    if parent.geometry is None:
        missing.append(parent.asset_id)
    missing.extend(
        asset_id
        for asset_id in sorted(affected)
        if asset_id not in known or known[asset_id].geometry is None
    )
    unresolved = (
        "No explicit registered asset-ID location relationship found in approved Story description",
    ) if not evidence else ()
    return CoordinatedSpatialPlan(
        story_id, parent.asset_id, evidence, tuple(missing), unresolved
    )
