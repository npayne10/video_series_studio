"""Read-only Shot evidence contract and conservative spatial evidence aggregation.

Shot text must be supplied by an authenticated project Shot reader. A Shot asset
binding is an identity constraint, not evidence of a physical relationship.
"""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.caps.narrative_spatial_resolution import (
    NarrativeSpatialResolution,
    resolve_narrative_spatial_relationships,
)
from vscs.domain.assets.models import Asset


@dataclass(frozen=True)
class ShotSpatialSource:
    shot_id: str
    story_id: str
    text: str
    bound_asset_ids: tuple[str, ...]


@dataclass(frozen=True)
class ShotSpatialFinding:
    shot_id: str
    story_id: str
    child_asset_id: str
    parent_asset_id: str
    excerpt: str
    start_offset: int
    source_kind: str = "shot_text_explicit_spatial_relation"


@dataclass(frozen=True)
class ShotSpatialPlan:
    findings: tuple[ShotSpatialFinding, ...]
    unresolved: tuple[str, ...]


def inspect_shot_spatial_evidence(
    sources: tuple[ShotSpatialSource, ...],
    registered_assets: tuple[Asset, ...],
    selected_story_id: str,
) -> ShotSpatialPlan:
    """Keep Shot ID, source and bindings; never expand evidence across projects."""
    findings: list[ShotSpatialFinding] = []
    unresolved: list[str] = []
    asset_by_id = {asset.asset_id: asset for asset in registered_assets}
    for source in sources:
        if source.story_id != selected_story_id:
            continue
        bound = set(source.bound_asset_ids)
        eligible = tuple(asset_by_id[key] for key in sorted(bound & asset_by_id.keys()))
        if not source.text.strip():
            unresolved.append(f"{source.shot_id}: Shot text unavailable; bindings are not prose")
            continue
        resolution: NarrativeSpatialResolution = resolve_narrative_spatial_relationships(
            source.story_id, source.text, eligible
        )
        for item in resolution.resolved:
            if item.child_asset_id in bound and item.parent_asset_id in bound:
                findings.append(
                    ShotSpatialFinding(
                        source.shot_id,
                        source.story_id,
                        item.child_asset_id,
                        item.parent_asset_id,
                        item.excerpt,
                        item.start_offset,
                    )
                )
        for ambiguous_item in resolution.ambiguous:
            unresolved.append(f"{source.shot_id}: ambiguous: {ambiguous_item.excerpt}")
    return ShotSpatialPlan(tuple(findings), tuple(unresolved))
