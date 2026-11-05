"""B.5.25: conservative, category-aware separation of asset identity and relationships.

This gate intentionally recognises a small set of unambiguous failures. It does
not infer new Canon, require a designed appearance, or approve a provider Draft.
"""

from __future__ import annotations

import re

from vscs.domain.assets.models import AssetCategory


def _match(pattern: str, value: str) -> bool:
    return re.search(pattern, value, flags=re.IGNORECASE | re.DOTALL) is not None


_SHIP = r"(?:ship|vessel|spacecraft|starship|shuttle|craft)"
_EXTERIOR = r"(?:hull|silhouette|outline|exterior|external\s+shape|outer\s+shape|form|profile)"
_UNKNOWN = r"(?:unresolved|unknown|unspecified|undetermined|not\s+(?:yet\s+)?established|not\s+(?:yet\s+)?defined)"
_LOCATION = r"(?:room|chamber|interior|location|environment|corridor|bay|bridge|facility)"
_LOCATION_STRUCTURE = r"(?:layout|walls?|floor|ceiling|door|space|contains?|houses?|arrangement|geometry|interior)"
_PROP = r"(?:console|workstation|terminal|device|instrument|equipment|prop|display\s+unit|control\s+panel)"
_PROP_STRUCTURE = r"(?:display|screen|housing|panel|buttons?|geometry|dimensions?|shape|surface|enclosure|controls?)"


def category_identity_issues(
    category: AssetCategory,
    asset_name: str,
    identity: str,
) -> tuple[str, ...]:
    """Return clear category-substitution issues in a persistent identity field.

    Explicit unresolved design is valid. A Ship must not use an interior console
    description as the hull/silhouette merely because the console is aboard it.
    A Location or Prop may describe its own composition and relationships without
    substituting the other asset for the subject.
    """
    value = identity.strip()
    if not value:
        return ("Missing asset identity; leave its physical design unresolved.",)

    if category in (AssetCategory.SHIP, AssetCategory.VEHICLE):
        ship_exterior = (
            _match(rf"\b{_SHIP}\b[^.\n]{{0,160}}\b{_EXTERIOR}\b", value)
            or _match(rf"\b{_EXTERIOR}\b[^.\n]{{0,160}}\b{_SHIP}\b", value)
        )
        unresolved_subject = (
            _match(rf"\b{_SHIP}\b[^.\n]{{0,160}}\b{_UNKNOWN}\b", value)
            or _match(rf"\b{_EXTERIOR}\b[^.\n]{{0,160}}\b{_UNKNOWN}\b", value)
        )
        if not ship_exterior and not unresolved_subject:
            return (
                f"{category.value} silhouette/visual identity describes contained "
                f"assets rather than the exterior identity of '{asset_name}'. "
                "Describe only evidenced hull/silhouette facts or explicitly leave "
                "the exterior unresolved. Keep room/equipment relationships in "
                "description or continuity, not the silhouette.",
            )
        # A sentence about an interior prop followed by a generic disclaimer
        # about unspecified exterior is not a usable ship silhouette.
        first_sentence = re.split(r"[.!?](?:\s|$)", value, maxsplit=1)[0]
        if _match(rf"\b{_PROP}\b", first_sentence) and not _match(
            rf"\b{_SHIP}\b[^.\n]{{0,90}}\b{_EXTERIOR}\b", first_sentence
        ):
            return (
                "Ship silhouette begins with a contained prop's appearance. "
                "Move the interior equipment relationship to narrative/continuity "
                "and make the vessel's supported exterior identity or unresolved "
                "exterior the primary silhouette statement.",
            )
    elif category is AssetCategory.LOCATION:
        if _match(rf"\b{_PROP}\b", value) and not _match(
            rf"\b{_LOCATION}\b[^.\n]{{0,130}}\b{_LOCATION_STRUCTURE}\b"
            rf"|\b{_LOCATION_STRUCTURE}\b[^.\n]{{0,130}}\b{_LOCATION}\b",
            value,
        ):
            if not _match(rf"\b{_LOCATION}\b[^.\n]{{0,120}}\b{_UNKNOWN}\b", value):
                return (
                    "Location architecture describes another asset rather than "
                    "the room or location. Describe the room's supported layout "
                    "or leave its architecture unresolved.",
                )
    elif category in (AssetCategory.PROP, AssetCategory.TECHNOLOGY):
        if _match(rf"\b{_LOCATION}\b", value) and not _match(
            rf"\b{_PROP}\b[^.\n]{{0,130}}\b{_PROP_STRUCTURE}\b"
            rf"|\b{_PROP_STRUCTURE}\b[^.\n]{{0,130}}\b{_PROP}\b",
            value,
        ):
            if not _match(rf"\b{_PROP}\b[^.\n]{{0,120}}\b{_UNKNOWN}\b", value):
                return (
                    "Prop/technology geometry describes its containing location "
                    "instead of the physical asset. Describe the prop's supported "
                    "geometry or leave it unresolved.",
                )
    return ()
