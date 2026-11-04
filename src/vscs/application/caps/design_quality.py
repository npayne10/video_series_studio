"""Advisory production-quality checks for unapproved CAP design proposals."""

from __future__ import annotations

import re
from dataclasses import dataclass

from vscs.application.caps.provider_design_expansion import ProposedDesignField
from vscs.domain.assets.models import AssetCategory

_CAMERA_SPACE = re.compile(
    r"\b(?:foreground|midground|background|in frame|camera angle|camera position|"
    r"camera-facing|left of camera|right of camera|toward camera|static shot|"
    r"wide shot|close-up|focal length|depth of field)\b",
    re.IGNORECASE,
)
_VAGUE_SCALE = re.compile(
    r"\b(?:human[- ]scaled|moderately sized|moderately confined|spacious|"
    r"comfortable|compact|large|small|enough room|feels? like)\b",
    re.IGNORECASE,
)
_MEASURED = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|metres?|meters?|ft|feet)\b", re.IGNORECASE)


@dataclass(frozen=True)
class DesignQualityIssue:
    field: str
    code: str
    message: str


def assess_design_quality(
    category: AssetCategory, items: tuple[ProposedDesignField, ...]
) -> tuple[DesignQualityIssue, ...]:
    """Flag physical continuity risks without granting or rejecting Canon."""
    issues: list[DesignQualityIssue] = []
    for item in items:
        value = item.proposed_value.strip()
        if _CAMERA_SPACE.search(value):
            issues.append(
                DesignQualityIssue(
                    item.field,
                    "camera_dependent",
                    "Define fixed asset geometry, not framing or camera-relative positions.",
                )
            )
        if item.field in {"scale", "dimensions"} and not _MEASURED.search(value):
            issues.append(
                DesignQualityIssue(
                    item.field,
                    "unmeasured_scale",
                    "Give proposed physical dimensions with units, clearly marked as design choices.",
                )
            )
        if item.field in {"layout", "spatial_anchors"} and _VAGUE_SCALE.search(value):
            issues.append(
                DesignQualityIssue(
                    item.field,
                    "imprecise_geometry",
                    "Specify stable relationships between named physical anchors.",
                )
            )
        if (
            category is AssetCategory.LOCATION
            and item.field == "layout"
            and "console" not in value.casefold()
            and "workstation" not in value.casefold()
        ):
            issues.append(
                DesignQualityIssue(
                    item.field,
                    "missing_functional_anchor",
                    "Check the required console/workstation against the approved Story.",
                )
            )
    return tuple(issues)


# B.5.25 — Guard source-grounding separately from creative design suitability.
# Only check patterns for which source-independent event ownership or a missing
# explicit spatial relation can be determined conservatively.
_SHOT_EVENT = re.compile(
    r"\b(?:indicator|light|display|screen)\b.{0,100}"
    r"\b(?:pulses?|flashes?|blinks?)\s+(?:exactly\s+)?once\b"
    r"|\b(?:after|before)\s+the\s+(?:indicator|light|display)\s+"
    r"(?:pulses?|flashes?|blinks?)\b"
    r"|\b(?:indicator|light|display)\b.{0,100}"
    r"\b(?:pulses?|flashes?|blinks?)\s+and\s+(?:then\s+)?returns?\b",
    re.IGNORECASE | re.DOTALL,
)
_INDICATOR_BY_DOOR = re.compile(
    r"\b(?:small\s+)?indicator\b.{0,90}\b(?:beside|by|next to|near|at|adjacent to)"
    r"\s+(?:the\s+|a\s+)?(?:doorway|door|hatch|entrance)\b"
    r"|\b(?:doorway|door|hatch|entrance)\b.{0,90}"
    r"\b(?:beside|by|next to|near|at|adjacent to)\s+(?:the\s+|a\s+)?"
    r"(?:small\s+)?indicator\b",
    re.IGNORECASE | re.DOTALL,
)


def assess_design_grounding(
    story_context: str, items: tuple[ProposedDesignField, ...]
) -> tuple[DesignQualityIssue, ...]:
    """Flag unsupported permanence/placement, without promoting creative proposals to canon.

    The Story is a grounding boundary, not a mandate to copy temporal Shot
    events into permanent asset design. Explicitly sourced door placement can
    be retained; otherwise the indicator's precise mounting is left open.
    """
    issues: list[DesignQualityIssue] = []
    for item in items:
        value = item.proposed_value
        if _SHOT_EVENT.search(value):
            issues.append(
                DesignQualityIssue(
                    item.field,
                    "transient_shot_event",
                    "One-time pulses, flashes and their timing belong in Shot plans, "
                    "not permanent CAP design details.",
                )
            )
        if _INDICATOR_BY_DOOR.search(value) and not _INDICATOR_BY_DOOR.search(story_context):
            issues.append(
                DesignQualityIssue(
                    item.field,
                    "unsupported_indicator_placement",
                    "A named indicator's placement beside a door is not supported "
                    "by the approved Story. Leave its precise attachment unresolved; "
                    "creative doorway design may still be proposed separately.",
                )
            )
    return tuple(issues)
