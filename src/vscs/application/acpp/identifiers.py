"""Stable identifier helpers for Advanced Clip Production Packages."""

from __future__ import annotations

import re

_IDENTIFIER_COMPONENT = re.compile(r"[^A-Za-z0-9_-]+")


def build_clip_id(
    production_id: str,
    scene_sequence_number: int,
    shot_sequence_number: int,
    clip_sequence_number: int = 1,
) -> str:
    """Build a deterministic clip identifier from production ordering."""
    normalized_production_id = _IDENTIFIER_COMPONENT.sub(
        "-",
        production_id.strip(),
    ).strip("-")
    if not normalized_production_id:
        raise ValueError("production_id must contain at least one identifier character")
    for field_name, value in (
        ("scene_sequence_number", scene_sequence_number),
        ("shot_sequence_number", shot_sequence_number),
        ("clip_sequence_number", clip_sequence_number),
    ):
        if value < 1:
            raise ValueError(f"{field_name} must be at least 1")
    return (
        f"{normalized_production_id}"
        f"-SC{scene_sequence_number:03d}"
        f"-SH{shot_sequence_number:03d}"
        f"-CL{clip_sequence_number:03d}"
    )
