from __future__ import annotations

from PySide6.QtWidgets import QApplication, QComboBox

from vscs.application.acpp.reference_roles import ReferenceRole
from vscs.presentation.widgets.governed_reference_suitability_guided_dialog import (
    COVERAGE_CHOICES,
    FRAMING_TYPE_CHOICES,
    GovernedReferenceSuitabilityGuidedDialog,
    _GuidedChoiceComboBox,
)


def test_guided_suitability_choices_expose_stable_governed_values() -> None:
    framing_values = {value for _label, value, _help in FRAMING_TYPE_CHOICES}
    coverage_values = {value for _label, value, _help in COVERAGE_CHOICES}

    assert {
        "unknown",
        "close_up",
        "head_and_shoulders",
        "medium_close",
        "medium",
        "three_quarter",
        "full_body",
        "full_asset",
        "wide_environment",
        "establishing",
        "scene_composition",
        "detail",
    } <= framing_values
    assert {
        "unknown",
        "identity_critical",
        "required_features",
        "full_required_asset",
        "partial_asset",
        "environment_context",
        "full_environment",
        "multi_subject",
        "scene_composition",
        "continuity_state",
        "start_frame",
        "end_frame",
    } <= coverage_values


def test_guided_choice_combo_persists_stable_values_and_preserves_legacy(
    qapp: QApplication,
) -> None:
    _ = qapp
    combo = _GuidedChoiceComboBox(FRAMING_TYPE_CHOICES)

    combo.setText("full_body")
    assert combo.text() == "full_body"
    assert combo.currentText() == "Full body"

    combo.setText("legacy_custom_framing")
    assert combo.text() == "legacy_custom_framing"
    assert combo.currentText() == "Legacy value: legacy_custom_framing"


def test_suitability_enum_combo_data_is_normalized_back_to_str_enum(
    qapp: QApplication,
) -> None:
    _ = qapp
    combo = QComboBox()
    combo.addItem("Primary identity", "primary_identity")

    resolved = GovernedReferenceSuitabilityGuidedDialog._combo_enum_value(
        combo,
        ReferenceRole,
        ReferenceRole.BACKGROUND_IDENTITY,
    )

    assert resolved is ReferenceRole.PRIMARY_IDENTITY
    assert resolved.value == "primary_identity"
