"""Certification matrix for onboarding keyboard and focus behaviour."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KeyboardFocusEvidence:
    """One certified keyboard or focus capability and its regression evidence."""

    area: str
    test_nodes: tuple[str, ...]


KEYBOARD_FOCUS_MATRIX = (
    KeyboardFocusEvidence(
        "Welcome keyboard entry",
        (
            "tests/certification/test_onboarding_keyboard_focus_certification.py::"
            "test_enter_starts_guide_from_welcome",
        ),
    ),
    KeyboardFocusEvidence(
        "Welcome focus containment",
        (
            "tests/certification/test_onboarding_keyboard_focus_certification.py::"
            "test_welcome_tab_navigation_stays_inside_overlay",
        ),
    ),
    KeyboardFocusEvidence(
        "Tour keyboard navigation",
        (
            "tests/certification/test_onboarding_keyboard_focus_certification.py::"
            "test_enter_and_space_navigate_tour",
        ),
    ),
    KeyboardFocusEvidence(
        "Tour focus containment",
        (
            "tests/certification/test_onboarding_keyboard_focus_certification.py::"
            "test_tour_tab_navigation_stays_inside_card",
        ),
    ),
    KeyboardFocusEvidence(
        "Try It focus handoff",
        (
            "tests/certification/test_onboarding_keyboard_focus_certification.py::"
            "test_space_activates_try_it_and_focuses_target",
        ),
    ),
    KeyboardFocusEvidence(
        "Uninterrupted identity entry",
        (
            "tests/certification/test_onboarding_keyboard_focus_certification.py::"
            "test_keyboard_identity_entry_is_not_interrupted",
            "tests/unit/test_guided_first_scene.py::"
            "test_required_scene_identity_step_waits_for_editing_to_finish",
        ),
    ),
    KeyboardFocusEvidence(
        "Focus restoration",
        (
            "tests/certification/test_onboarding_keyboard_focus_certification.py::"
            "test_skipping_welcome_releases_focus_to_editor",
        ),
    ),
    KeyboardFocusEvidence(
        "Escape recovery",
        (
            "tests/certification/test_onboarding_keyboard_focus_certification.py::"
            "test_escape_closes_scene_editor_without_focus_trap",
        ),
    ),
    KeyboardFocusEvidence(
        "Checklist keyboard activation",
        (
            "tests/unit/test_guided_workflow_navigation.py::"
            "test_checklist_button_supports_keyboard_activation",
        ),
    ),
)


def keyboard_focus_areas() -> tuple[str, ...]:
    """Return certified areas in report order."""
    return tuple(evidence.area for evidence in KEYBOARD_FOCUS_MATRIX)


def keyboard_focus_test_nodes() -> tuple[str, ...]:
    """Return deduplicated regression nodes in stable order."""
    return tuple(
        dict.fromkeys(
            node
            for evidence in KEYBOARD_FOCUS_MATRIX
            for node in evidence.test_nodes
        )
    )
