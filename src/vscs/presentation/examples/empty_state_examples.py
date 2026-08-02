"""Reusable empty-state guidance for VSCS editors."""

from __future__ import annotations

EMPTY_STATE_FALLBACK = (
    "Nothing is available yet. Add the required project data, then return to this field."
)


def empty_state_text(value: str | None) -> str:
    """Return a useful empty-state message with a safe fallback."""
    normalized = (value or "").strip()
    return normalized or EMPTY_STATE_FALLBACK
