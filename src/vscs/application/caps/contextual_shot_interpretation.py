"""Conservative offline contextual Shot relationship suggestions (never Canon)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from vscs.application.caps.shot_spatial_evidence import ShotSpatialSource
from vscs.domain.assets.models import Asset

_PREPOSITION = re.compile(
    r"(?P<child>[\w][\w '\-]{1,90}?)\s+"
    r"(?:stands|sits|rests|glows|pulses|remains|is|appears)?\s*"
    r"(?:in|within|inside|aboard)\s+"
    r"(?P<parent>[\w][\w '\-]{1,90}?)(?=[.,;!?]|$)",
    re.IGNORECASE,
)
_STOP = re.compile(r"\\b(?:no|without|not|never)\\b", re.IGNORECASE)
_LOCATION_FIRST = re.compile(
    r"(?:^|[.!?]\\s+)In\\s+(?:the\\s+)?"
    r"(?P<parent>[^,.;!?]{2,100}),\\s+"
    r"(?:the\\s+)?(?P<child>[^,.;!?]{2,120}?)(?=[,.;!?]|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ContextualShotSuggestion:
    shot_id: str
    child_asset_id: str
    parent_asset_id: str
    excerpt: str
    confidence: str = "review_required"


def _names(text: str, assets: tuple[Asset, ...]) -> tuple[str, ...]:
    matches = [
        (len(asset.name), asset.asset_id)
        for asset in assets
        if asset.name.strip()
        and re.search(r"(?<!\w)" + re.escape(asset.name) + r"(?!\w)", text, re.IGNORECASE)
    ]
    if not matches:
        return ()
    maximum = max(length for length, _ in matches)
    return tuple(sorted(asset_id for length, asset_id in matches if length == maximum))


def suggest_contextual_shot_relationships(
    sources: tuple[ShotSpatialSource, ...],
    assets: tuple[Asset, ...],
    story_id: str,
) -> tuple[ContextualShotSuggestion, ...]:
    """Only exact registered names and Shot bindings; never infer unnamed objects.

    B.5.20 suggestions remain advisory, even for verified source text.
    """
    by_id = {asset.asset_id: asset for asset in assets}
    output: list[ContextualShotSuggestion] = []
    for source in sources:
        if source.story_id != story_id:
            continue
        eligible = tuple(
            by_id[asset_id] for asset_id in source.bound_asset_ids if asset_id in by_id
        )
        for match in _PREPOSITION.finditer(source.text):
            excerpt = match.group(0)
            if _STOP.search(excerpt):
                continue
            children = _names(match.group("child"), eligible)
            parents = _names(match.group("parent"), eligible)
            if len(children) != 1 or len(parents) != 1 or children[0] == parents[0]:
                continue
            suggestion = ContextualShotSuggestion(
                source.shot_id, children[0], parents[0], excerpt
            )
            if suggestion not in output:
                output.append(suggestion)
        for match in _LOCATION_FIRST.finditer(source.text):
            parent_ids = _names(match.group("parent"), eligible)
            child_ids = _names(match.group("child"), eligible)
            if len(parent_ids) != 1 or len(child_ids) != 1:
                continue
            if parent_ids[0] == child_ids[0]:
                continue
            suggestion = ContextualShotSuggestion(
                source.shot_id,
                child_ids[0],
                parent_ids[0],
                match.group(0).strip(),
            )
            if suggestion not in output:
                output.append(suggestion)
    return tuple(output)
