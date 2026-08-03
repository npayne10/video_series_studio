"""Certification evidence for onboarding accessibility and visual consistency."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccessibilityVisualEvidence:
    """One certified accessibility or visual-consistency area."""

    area: str
    test_nodes: tuple[str, ...]


ACCESSIBILITY_VISUAL_MATRIX = (
    AccessibilityVisualEvidence(
        "Accessible onboarding identity",
        (
            "tests/certification/test_onboarding_accessibility_visual_certification.py::test_onboarding_surfaces_have_accessible_names",
        ),
    ),
    AccessibilityVisualEvidence(
        "Descriptive controls",
        (
            "tests/certification/test_onboarding_accessibility_visual_certification.py::test_primary_controls_have_names_and_tooltips",
        ),
    ),
    AccessibilityVisualEvidence(
        "Stable object names",
        (
            "tests/certification/test_onboarding_accessibility_visual_certification.py::test_certified_object_names_are_unique_and_stable",
        ),
    ),
    AccessibilityVisualEvidence(
        "Consistent action language",
        (
            "tests/certification/test_onboarding_accessibility_visual_certification.py::test_onboarding_action_language_is_consistent",
        ),
    ),
    AccessibilityVisualEvidence(
        "Visible keyboard focus",
        (
            "tests/certification/test_onboarding_accessibility_visual_certification.py::test_visible_overlays_assign_focus_to_an_action",
            "tests/certification/test_onboarding_keyboard_focus_certification.py",
        ),
    ),
    AccessibilityVisualEvidence(
        "Palette resilience",
        (
            "tests/certification/test_onboarding_accessibility_visual_certification.py::test_onboarding_renders_with_light_and_dark_palettes",
        ),
    ),
    AccessibilityVisualEvidence(
        "Beginner and expert consistency",
        (
            "tests/certification/test_onboarding_accessibility_visual_certification.py::test_beginner_and_expert_modes_preserve_core_workspace",
            "tests/unit/test_beginner_mode_persistence.py",
        ),
    ),
    AccessibilityVisualEvidence(
        "Readable validation state",
        (
            "tests/certification/test_onboarding_accessibility_visual_certification.py::test_validation_status_is_textual_not_colour_only",
            "tests/unit/test_validation_explanations.py",
        ),
    ),
)


def accessibility_visual_areas() -> tuple[str, ...]:
    """Return certification areas in approved order."""
    return tuple(evidence.area for evidence in ACCESSIBILITY_VISUAL_MATRIX)


def accessibility_visual_test_nodes() -> tuple[str, ...]:
    """Return unique regression nodes referenced by the matrix."""
    return tuple(
        dict.fromkeys(
            node
            for evidence in ACCESSIBILITY_VISUAL_MATRIX
            for node in evidence.test_nodes
        )
    )
