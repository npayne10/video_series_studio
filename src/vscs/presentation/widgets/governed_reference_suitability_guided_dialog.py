"""Guided choice fields for governed reference-suitability review."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from vscs.application.acpp.reference_roles import (
    ReferenceClass,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
)

from .governed_reference_suitability_review_dialog import (
    GovernedReferenceSuitabilityReviewDialog,
)

FRAMING_TYPE_CHOICES: tuple[tuple[str, str, str], ...] = (
    ("Unknown / not reviewed", "unknown", "Use only until the framing has been reviewed."),
    ("Close-up", "close_up", "Face or small identity-critical detail dominates the frame."),
    ("Head and shoulders", "head_and_shoulders", "Head, shoulders and upper chest are visible."),
    ("Medium close", "medium_close", "Approximately chest or waist-up subject framing."),
    ("Medium", "medium", "Subject is shown with useful body and surrounding context."),
    ("Three-quarter", "three_quarter", "Most of a person or object is visible, but not fully."),
    ("Full body", "full_body", "The complete person is visible from head to feet."),
    ("Full asset", "full_asset", "The complete ship, prop, vehicle or other asset is visible."),
    ("Wide environment", "wide_environment", "Environment dominates with broad spatial context."),
    ("Establishing", "establishing", "Wide spatial reference used to establish the location."),
    ("Scene composition", "scene_composition", "Reviewed multi-subject shot composition."),
    ("Detail", "detail", "A specific feature or component is intentionally isolated."),
)

COVERAGE_CHOICES: tuple[tuple[str, str, str], ...] = (
    ("Unknown / not reviewed", "unknown", "Use only until coverage has been reviewed."),
    (
        "Identity critical",
        "identity_critical",
        "Covers the subject features needed to preserve identity.",
    ),
    (
        "Required features",
        "required_features",
        "Covers all features specifically required by the Shot.",
    ),
    (
        "Full required asset",
        "full_required_asset",
        "Covers the complete governed asset needed by the Shot.",
    ),
    ("Partial asset", "partial_asset", "Only part of the governed asset is visible."),
    (
        "Environment context",
        "environment_context",
        "Provides contextual location/environment information.",
    ),
    (
        "Full environment",
        "full_environment",
        "Provides broad coverage of the required environment.",
    ),
    ("Multi-subject", "multi_subject", "One reference covers multiple governed subjects."),
    (
        "Scene composition",
        "scene_composition",
        "Covers the governed spatial relationship of a complete scene.",
    ),
    (
        "Continuity state",
        "continuity_state",
        "Captures a reviewed visual state carried between Shots.",
    ),
    ("Start frame", "start_frame", "Covers the exact governed starting frame state."),
    ("End frame", "end_frame", "Covers the exact governed ending frame state."),
)


class _GuidedChoiceComboBox(QComboBox):
    """Fixed-choice combo compatible with the legacy line-edit API used by the base dialog."""

    def __init__(
        self,
        choices: Iterable[tuple[str, str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        for label, value, help_text in choices:
            self.addItem(label, value)
            index = self.count() - 1
            self.setItemData(index, help_text, role=3)  # Qt.ToolTipRole
        self.setEditable(False)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

    def text(self) -> str:
        """Return the persisted stable value expected by the base dialog."""
        value = self.currentData()
        return str(value if value is not None else self.currentText())

    def setText(self, value: str) -> None:  # noqa: N802 - compatibility with QLineEdit API
        """Select a persisted value, retaining unknown legacy values safely."""
        normalized = str(value or "unknown")
        for index in range(self.count()):
            if str(self.itemData(index)) == normalized:
                self.setCurrentIndex(index)
                return
        self.addItem(f"Legacy value: {normalized}", normalized)
        self.setCurrentIndex(self.count() - 1)


class GovernedReferenceSuitabilityGuidedDialog(GovernedReferenceSuitabilityReviewDialog):
    """Replace free-text suitability classification fields with guided dropdown choices."""

    def _build_ui(self) -> None:
        super()._build_ui()
        self.framing_type = self._replace_with_choice_combo(
            self.framing_type,
            FRAMING_TYPE_CHOICES,
            "Choose how the reviewed subject/environment is framed in this reference.",
        )
        self.coverage = self._replace_with_choice_combo(
            self.coverage,
            COVERAGE_CHOICES,
            "Choose what governed visual requirement this reference actually covers.",
        )
        self.framing_type.currentIndexChanged.connect(self._editor_changed)
        self.coverage.currentIndexChanged.connect(self._editor_changed)

    def _editor_changed(self, *_args: object) -> None:
        """Persist editor values while normalizing Qt round-tripped StrEnum data."""
        if self._loading_editor or not (0 <= self._current_row < len(self._states)):
            return
        state = self._states[self._current_row]
        state.reference_id = self.reference_id.text().strip()
        state.label = self.label_edit.text().strip()
        state.role = self._combo_enum_value(
            self.role_combo,
            ReferenceRole,
            self._enum_value(ReferenceRole, state.role, ReferenceRole.BACKGROUND_IDENTITY),
        )
        state.reference_class = self._combo_enum_value(
            self.class_combo,
            ReferenceClass,
            self._enum_value(
                ReferenceClass,
                state.reference_class,
                ReferenceClass.CANONICAL_MASTER,
            ),
        )
        state.subject_type = self._combo_enum_value(
            self.subject_combo,
            ReferenceSubjectType,
            self._enum_value(
                ReferenceSubjectType,
                state.subject_type,
                ReferenceSubjectType.OTHER,
            ),
        )
        state.priority = self._combo_enum_value(
            self.priority_combo,
            ReferencePriority,
            self._enum_value(
                ReferencePriority,
                state.priority,
                ReferencePriority.REQUIRED,
            ),
        )
        state.provider_ready = self.provider_ready.isChecked()
        state.provider_profiles = self.provider_profiles.text().strip()
        state.framing_type = self.framing_type.text().strip()
        state.coverage = self.coverage.text().strip()
        state.required_features_visible = self.features_visible.isChecked()
        state.identity_visible = self.identity_visible.isChecked()
        state.full_required_asset_visible = self.full_asset_visible.isChecked()
        state.contains_subjects = self.contains_subjects.text().strip()
        state.contains_props = self.contains_props.text().strip()
        state.contains_environments = self.contains_environments.text().strip()
        state.review_note = self.review_note.toPlainText().strip()
        self._refresh_table_row(self._current_row)

    @staticmethod
    def _combo_enum_value(combo: QComboBox, enum_type: type[Any], default: Any) -> Any:
        """Convert QVariant-backed combo data back to its governed StrEnum type."""
        raw = combo.currentData()
        try:
            return enum_type(str(raw or ""))
        except ValueError:
            return default

    @staticmethod
    def _replace_with_choice_combo(
        old_widget: QWidget,
        choices: Iterable[tuple[str, str, str]],
        tooltip: str,
    ) -> _GuidedChoiceComboBox:
        parent = old_widget.parentWidget()
        if parent is None or not isinstance(parent.layout(), QFormLayout):
            raise RuntimeError("Suitability choice field is not hosted by the expected form layout")
        form = parent.layout()
        row, role = form.getWidgetPosition(old_widget)
        if row < 0:
            raise RuntimeError("Suitability choice field could not be located in the form layout")
        combo = _GuidedChoiceComboBox(choices, parent)
        combo.setToolTip(tooltip)
        form.removeWidget(old_widget)
        old_widget.hide()
        old_widget.deleteLater()
        form.setWidget(row, role, combo)
        return combo
