"""Guided choice fields for governed reference-suitability review."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.acpp.reference_roles import (
    ReferenceClass,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
)
from vscs.application.governed_reference_suitability_review import (
    suggested_reference_priority,
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

_LTX_PROVIDER_IDS = frozenset({"ltx23-local", "ltx23", "ltx-2.3"})
_LTX_VISUAL_REFERENCE_LIMIT = 3
_NON_DIRECT_VISUAL_ROLE_VALUES = frozenset(
    {
        "scene_composition_anchor",
        "provider_helper_reference",
        "start_frame_reference",
        "continuity_reference",
        "previous_shot_final_frame",
    }
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
    """Add guided classification and provider-capacity review to suitability authoring."""

    def _build_ui(self) -> None:
        super()._build_ui()
        framing_combo = self._replace_with_choice_combo(
            self.framing_type,
            FRAMING_TYPE_CHOICES,
            "Choose how the reviewed subject/environment is framed in this reference.",
        )
        coverage_combo = self._replace_with_choice_combo(
            self.coverage,
            COVERAGE_CHOICES,
            "Choose what governed visual requirement this reference actually covers.",
        )
        guided_self = cast(Any, self)
        guided_self.framing_type = framing_combo
        guided_self.coverage = coverage_combo
        framing_combo.currentIndexChanged.connect(self._editor_changed)
        coverage_combo.currentIndexChanged.connect(self._editor_changed)

        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderItem(8, QTableWidgetItem("Priority"))

        list_panel = self.table.parentWidget()
        list_layout = list_panel.layout() if list_panel is not None else None
        if not isinstance(list_layout, QVBoxLayout):
            raise RuntimeError("Suitability reference list layout is unavailable")

        self.capacity_status = QLabel(list_panel)
        self.capacity_status.setWordWrap(True)
        self.capacity_status.setObjectName("reference_capacity_status")
        self.apply_suggested_priorities_button = QPushButton(
            "Apply Suggested Priorities",
            list_panel,
        )
        self.apply_suggested_priorities_button.setObjectName(
            "apply_suggested_reference_priorities_button"
        )
        self.apply_suggested_priorities_button.setToolTip(
            "Apply production-semantic REQUIRED/PREFERRED suggestions to included canonical "
            "candidates. Existing explicit authority is changed only when you click this button "
            "and later save/approve the review."
        )

        capacity_row = QHBoxLayout()
        capacity_row.addWidget(self.capacity_status, 1)
        capacity_row.addWidget(self.apply_suggested_priorities_button)
        table_index = list_layout.indexOf(self.table)
        list_layout.insertLayout(table_index + 1, capacity_row)

        self.apply_suggested_priorities_button.clicked.connect(
            self._apply_suggested_priorities
        )
        self.target_provider.textChanged.connect(self._update_action_state)

    def _populate_table(self) -> None:
        super()._populate_table()
        self._refresh_priority_column()

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
        self._update_action_state()

    def _refresh_table_row(self, row: int) -> None:
        super()._refresh_table_row(row)
        self._refresh_priority_cell(row)

    def _refresh_priority_column(self) -> None:
        for row in range(len(self._states)):
            self._refresh_priority_cell(row)

    def _refresh_priority_cell(self, row: int) -> None:
        if not (0 <= row < len(self._states)):
            return
        item = self.table.item(row, 8)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(row, 8, item)
        item.setText(self._states[row].priority.value)

    def _apply_suggested_priorities(self) -> None:
        changed = 0
        for state in self._states:
            if not state.included or state.custom:
                continue
            suggested = suggested_reference_priority(state.category, state.semantic_role)
            if state.priority is not suggested:
                state.priority = suggested
                changed += 1

        self._refresh_priority_column()
        if 0 <= self._current_row < len(self._states):
            self._loading_editor = True
            try:
                self._select_enum(
                    self.priority_combo,
                    self._states[self._current_row].priority,
                )
            finally:
                self._loading_editor = False

        self._update_action_state()
        if changed:
            self.capacity_status.setToolTip(
                f"Applied {changed} semantic priority suggestion(s). "
                "Review the result before saving or approving."
            )

    def _update_action_state(self, *_args: object) -> None:
        super()._update_action_state()
        if not hasattr(self, "capacity_status"):
            return

        self._refresh_priority_column()
        included_candidates = [
            state for state in self._states if state.included and not state.custom
        ]
        self.apply_suggested_priorities_button.setEnabled(bool(included_candidates))

        provider_id = self.target_provider.text().strip().lower()
        if provider_id not in _LTX_PROVIDER_IDS:
            self.capacity_status.setText(
                "Provider capacity: no LTX direct-reference limit is enforced by this review."
            )
            return

        direct_visual = [
            state
            for state in self._states
            if state.included and state.role.value not in _NON_DIRECT_VISUAL_ROLE_VALUES
        ]
        required = [
            state for state in direct_visual if state.priority is ReferencePriority.REQUIRED
        ]
        preferred_ready = [
            state
            for state in direct_visual
            if state.priority is ReferencePriority.PREFERRED and state.provider_ready
        ]
        planned_direct = min(
            _LTX_VISUAL_REFERENCE_LIMIT,
            len(required) + len(preferred_ready),
        )

        if not required:
            self.capacity_status.setText(
                "LTX direct visual capacity: required 0/3 — BLOCKED. "
                "At least one required governed visual reference is required."
            )
            self.approve_button.setEnabled(False)
            return

        if len(required) > _LTX_VISUAL_REFERENCE_LIMIT:
            self.capacity_status.setText(
                "LTX direct visual capacity: "
                f"required {len(required)}/{_LTX_VISUAL_REFERENCE_LIMIT}; "
                f"preferred {len(preferred_ready)} — OVER CAPACITY. "
                "Required references are never silently dropped."
            )
            self.approve_button.setEnabled(False)
            return

        self.capacity_status.setText(
            "LTX direct visual capacity: "
            f"required {len(required)}/{_LTX_VISUAL_REFERENCE_LIMIT}; "
            f"preferred {len(preferred_ready)}; "
            f"planned direct slots {planned_direct}/{_LTX_VISUAL_REFERENCE_LIMIT} — PASS."
        )

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
        if parent is None:
            raise RuntimeError("Suitability choice field is not hosted by the expected form layout")
        form = parent.layout()
        if not isinstance(form, QFormLayout):
            raise RuntimeError("Suitability choice field is not hosted by the expected form layout")
        row, role = cast(tuple[int, Any], form.getWidgetPosition(old_widget))
        if row < 0:
            raise RuntimeError("Suitability choice field could not be located in the form layout")
        combo = _GuidedChoiceComboBox(choices, parent)
        combo.setToolTip(tooltip)
        form.removeWidget(old_widget)
        old_widget.hide()
        old_widget.deleteLater()
        form.setWidget(row, role, combo)
        return combo
