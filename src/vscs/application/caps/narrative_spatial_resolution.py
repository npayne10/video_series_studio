"""Evidence-only resolution of ordinary narrative names to registered project assets."""

from __future__ import annotations

import re
from dataclasses import dataclass

from vscs.domain.assets.models import Asset

_SPATIAL = re.compile(
    r"(?P<child>[\w][\w '\-]{1,90}?)\s+"
    r"(?:is\s+)?(?:located\s+in|inside|within)\s+"
    r"(?P<parent>[\w][\w '\-]{1,90}?)(?=[.,;!?]|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResolvedNarrativeRelation:
    child_asset_id: str
    parent_asset_id: str
    excerpt: str
    start_offset: int
    story_id: str
    source_kind: str = "approved_story_description_registered_names"


@dataclass(frozen=True)
class AmbiguousNarrativeRelation:
    excerpt: str
    start_offset: int
    candidate_child_ids: tuple[str, ...]
    candidate_parent_ids: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeSpatialResolution:
    resolved: tuple[ResolvedNarrativeRelation, ...]
    ambiguous: tuple[AmbiguousNarrativeRelation, ...]


def _mentions(text: str, assets: tuple[Asset, ...]) -> tuple[str, ...]:
    """Exact phrase matches, longest match wins; never guess from partial words."""
    matches = []
    for asset in assets:
        label = asset.name.strip()
        if label and re.search(r"(?<!\w)" + re.escape(label) + r"(?!\w)", text, re.IGNORECASE):
            matches.append((len(label), asset.asset_id))
    if not matches:
        return ()
    longest = max(length for length, _ in matches)
    return tuple(sorted(asset_id for length, asset_id in matches if length == longest))


def resolve_narrative_spatial_relationships(
    story_id: str,
    description: str,
    assets: tuple[Asset, ...],
) -> NarrativeSpatialResolution:
    """Only explicit 'X inside Y' name relationships; ambiguities never auto-apply."""
    resolved: list[ResolvedNarrativeRelation] = []
    ambiguous: list[AmbiguousNarrativeRelation] = []
    for match in _SPATIAL.finditer(description):
        child_ids = _mentions(match.group("child"), assets)
        parent_ids = _mentions(match.group("parent"), assets)
        if not child_ids or not parent_ids:
            continue
        excerpt = match.group(0)
        if len(child_ids) != 1 or len(parent_ids) != 1 or child_ids[0] == parent_ids[0]:
            ambiguous.append(
                AmbiguousNarrativeRelation(excerpt, match.start(), child_ids, parent_ids)
            )
            continue
        resolved.append(
            ResolvedNarrativeRelation(
                child_ids[0], parent_ids[0], excerpt, match.start(), story_id
            )
        )
    return NarrativeSpatialResolution(tuple(resolved), tuple(ambiguous))
