"""Certification evidence for onboarding overlay and spotlight behaviour."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverlaySpotlightEvidence:
    """One certified overlay or spotlight behaviour and its regression evidence."""

    area: str
    test_nodes: tuple[str, ...]


_CERTIFICATION_FILE = (
    "tests/certification/"
    "test_onboarding_overlay_spotlight_certification.py"
)

OVERLAY_SPOTLIGHT_MATRIX = (
    OverlaySpotlightEvidence(
        "Welcome overlay coverage",
        (
            f"{_CERTIFICATION_FILE}::"
            "test_welcome_overlay_covers_dialog_and_card_stays_inside",
        ),
    ),
    OverlaySpotlightEvidence(
        "Tour overlay coverage",
        (
            f"{_CERTIFICATION_FILE}::"
            "test_tour_overlay_covers_dialog_after_resize",
        ),
    ),
    OverlaySpotlightEvidence(
        "Spotlight target accuracy",
        (
            f"{_CERTIFICATION_FILE}::"
            "test_spotlight_contains_the_navigated_target",
            "tests/unit/test_guided_interface_tour.py",
        ),
    ),
    OverlaySpotlightEvidence(
        "Card collision avoidance",
        (
            f"{_CERTIFICATION_FILE}::"
            "test_tour_card_avoids_a_top_right_spotlight",
        ),
    ),
    OverlaySpotlightEvidence(
        "Missing target recovery",
        (
            f"{_CERTIFICATION_FILE}::"
            "test_missing_or_hidden_target_clears_spotlight_safely",
        ),
    ),
    OverlaySpotlightEvidence(
        "Scrolling and spotlight refresh",
        (
            f"{_CERTIFICATION_FILE}::"
            "test_spotlight_tracks_target_after_guided_scrolling",
        ),
    ),
    OverlaySpotlightEvidence(
        "Focus-safe redraw",
        (
            f"{_CERTIFICATION_FILE}::"
            "test_overlay_resize_keeps_tour_focus_and_geometry",
            "tests/certification/test_onboarding_keyboard_focus_certification.py",
        ),
    ),
)


def overlay_spotlight_areas() -> tuple[str, ...]:
    """Return certification areas in approved order."""
    return tuple(evidence.area for evidence in OVERLAY_SPOTLIGHT_MATRIX)


def overlay_spotlight_test_nodes() -> tuple[str, ...]:
    """Return unique regression nodes referenced by the matrix."""
    return tuple(
        dict.fromkeys(
            node
            for evidence in OVERLAY_SPOTLIGHT_MATRIX
            for node in evidence.test_nodes
        )
    )
