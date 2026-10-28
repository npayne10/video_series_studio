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
