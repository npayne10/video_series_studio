"""Certification requirements for responsive Scene Editor layout behaviour."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponsiveLayoutEvidence:
    """One responsive-layout requirement and its automated evidence."""

    area: str
    requirement: str
    test_node: str


RESPONSIVE_LAYOUT_MATRIX: tuple[ResponsiveLayoutEvidence, ...] = (
    ResponsiveLayoutEvidence(
        "Compact laptop layout",
        "The Scene Editor remains usable at 800 x 640 with fixed actions visible.",
        (
            "tests/certification/test_onboarding_responsive_layout_certification.py::"
            "test_compact_layout_keeps_editor_scrollable_and_actions_visible"
        ),
    ),
    ResponsiveLayoutEvidence(
        "Standard desktop layout",
        "The central editor receives the dominant share of the vertical workspace.",
        (
            "tests/certification/test_onboarding_responsive_layout_certification.py::"
            "test_standard_layout_prioritises_the_editor"
        ),
    ),
    ResponsiveLayoutEvidence(
        "Large desktop layout",
        "Additional space expands the editor without forcing support panels open.",
        (
            "tests/certification/test_onboarding_responsive_layout_certification.py::"
            "test_large_layout_preserves_compact_support_panels"
        ),
    ),
    ResponsiveLayoutEvidence(
        "Live resize",
        "Repeated resize transitions retain splitters, controls and editor usability.",
        (
            "tests/certification/test_onboarding_responsive_layout_certification.py::"
            "test_live_resize_preserves_workspace_structure"
        ),
    ),
    ResponsiveLayoutEvidence(
        "Welcome overlay fit",
        "The first-run overlay follows the complete dialog geometry after resizing.",
        (
            "tests/certification/test_onboarding_responsive_layout_certification.py::"
            "test_welcome_overlay_tracks_dialog_geometry"
        ),
    ),
    ResponsiveLayoutEvidence(
        "Tour overlay fit",
        "The guided-tour overlay and card remain inside the resized dialog.",
        (
            "tests/certification/test_onboarding_responsive_layout_certification.py::"
            "test_tour_overlay_and_card_fit_resized_dialog"
        ),
    ),
    ResponsiveLayoutEvidence(
        "Responsive persistence",
        "Panel and splitter preferences restore after reopening at another size.",
        (
            "tests/certification/test_onboarding_responsive_layout_certification.py::"
            "test_responsive_layout_state_restores_at_a_different_window_size"
        ),
    ),
)


def responsive_layout_areas() -> tuple[str, ...]:
    """Return certification areas in their approved order."""
    return tuple(evidence.area for evidence in RESPONSIVE_LAYOUT_MATRIX)


def responsive_layout_test_nodes() -> tuple[str, ...]:
    """Return the executable evidence nodes."""
    return tuple(evidence.test_node for evidence in RESPONSIVE_LAYOUT_MATRIX)
