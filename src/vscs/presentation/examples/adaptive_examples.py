"""Adaptive production examples derived from project asset names."""

from __future__ import annotations


def heading_suggestions(prefix: str, locations: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Return non-binding screenplay-heading suggestions for a typed prefix."""
    normalized = prefix.strip().upper()
    if not normalized.startswith(("INT", "EXT")):
        return ()

    interior = normalized.startswith("INT")
    defaults = (
        "INT. MAURITANIA BRIDGE - NIGHT",
        "INT. ENGINEERING - DAY",
        "INT. SHUTTLE - CONTINUOUS",
    ) if interior else (
        "EXT. XORIX SPACEPORT - DAY",
        "EXT. FOREST CLEARING - DUSK",
        "EXT. ORBITAL PLATFORM - NIGHT",
    )
    asset_suggestions = tuple(
        f"{'INT.' if interior else 'EXT.'} {name.upper()} - "
        f"{'NIGHT' if interior else 'DAY'}"
        for name in locations[:5]
    )
    candidates = asset_suggestions + defaults
    return tuple(dict.fromkeys(candidates))


def scene_name_examples(
    locations: tuple[str, ...] = (),
    characters: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Return project-aware scene-name examples before generic fallbacks."""
    dynamic: list[str] = []
    if locations:
        dynamic.extend((f"Arrival at {locations[0]}", f"Approach to {locations[0]}"))
    if len(characters) >= 2:
        dynamic.append(f"{characters[0]} Briefs {characters[1]}")
    return tuple(dynamic)
