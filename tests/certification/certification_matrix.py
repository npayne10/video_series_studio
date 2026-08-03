"""Functional certification matrix for the VSCS onboarding framework."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CertificationEvidence:
    """One functional area and the regression tests that certify it."""

    area: str
    test_nodes: tuple[str, ...]


ONBOARDING_FUNCTIONAL_MATRIX: tuple[CertificationEvidence, ...] = (
    CertificationEvidence(
        "Welcome Experience",
        (
            "tests/unit/test_scene_editor_welcome_experience.py",
            "tests/unit/test_onboarding_framework.py",
        ),
    ),
    CertificationEvidence(
        "Beginner Mode",
        ("tests/unit/test_beginner_mode_persistence.py",),
    ),
    CertificationEvidence(
        "Guided Tour",
        ("tests/unit/test_guided_interface_tour.py",),
    ),
    CertificationEvidence(
        "Guided Navigation",
        ("tests/unit/test_guided_workflow_navigation.py",),
    ),
    CertificationEvidence(
        "Guided First Scene",
        ("tests/unit/test_guided_first_scene.py",),
    ),
    CertificationEvidence(
        "Try It Workflow",
        (
            "tests/unit/test_guided_first_scene.py::"
            "test_required_scene_identity_step_waits_for_editing_to_finish",
            "tests/unit/test_guided_first_scene.py::"
            "test_validation_try_it_focuses_first_missing_field",
        ),
    ),
    CertificationEvidence(
        "Validation",
        ("tests/unit/test_validation_explanations.py",),
    ),
    CertificationEvidence(
        "VKF Integration",
        (
            "tests/unit/test_knowledge_framework.py",
            "tests/unit/test_example_provider.py",
            "tests/unit/test_live_documentation_panel.py",
        ),
    ),
    CertificationEvidence(
        "Adaptive Workspace",
        ("tests/unit/test_adaptive_workspace_layout.py",),
    ),
    CertificationEvidence(
        "Persistence",
        (
            "tests/unit/test_onboarding_framework.py",
            "tests/unit/test_beginner_mode_persistence.py",
            "tests/unit/test_adaptive_workspace_layout.py",
        ),
    ),
    CertificationEvidence(
        "Recovery",
        (
            "tests/unit/test_scene_editor_welcome_experience.py",
            "tests/unit/test_guided_interface_tour.py",
            "tests/unit/test_scene_editor_dialog.py",
        ),
    ),
)


def certification_areas() -> tuple[str, ...]:
    """Return the ordered functional certification areas."""
    return tuple(evidence.area for evidence in ONBOARDING_FUNCTIONAL_MATRIX)


def certification_test_nodes() -> tuple[str, ...]:
    """Return de-duplicated regression nodes in stable matrix order."""
    nodes: list[str] = []
    for evidence in ONBOARDING_FUNCTIONAL_MATRIX:
        for node in evidence.test_nodes:
            if node not in nodes:
                nodes.append(node)
    return tuple(nodes)
