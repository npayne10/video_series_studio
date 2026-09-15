from __future__ import annotations

from PySide6.QtWidgets import QApplication

from vscs.presentation.widgets.governed_reference_suitability_guided_dialog import (
    COVERAGE_CHOICES,
    FRAMING_TYPE_CHOICES,
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
