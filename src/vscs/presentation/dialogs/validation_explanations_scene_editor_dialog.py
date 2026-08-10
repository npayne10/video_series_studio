"""Scene Editor with explanatory, actionable validation feedback."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.production_container_scene_editor_dialog import (
    ProductionContainerSceneEditorDialog,
)


class ValidationSeverity(StrEnum):
    """User-facing validation severity."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ValidationExplanation:
    """One actionable Scene Editor validation result."""

    field_name: str
    message: str
    reason: str
    topic_id: str
    widget: QWidget
    severity: ValidationSeverity = ValidationSeverity.ERROR


class ValidationExplanationsSceneEditorDialog(ProductionContainerSceneEditorDialog):
    """Explain what is incomplete, why it matters, and how to resolve it."""

    _CONTAINER_PATTERN = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        self.validation_explanations: tuple[ValidationExplanation, ...] = ()
        super().__init__(scene, parent, **kwargs)
        self.validation_label.setObjectName("sceneValidationExplanations")
        self.validation_label.setTextFormat(Qt.TextFormat.RichText)
        self.validation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.validation_label.setAccessibleName("Scene validation explanations")
        self.participant_list.itemChanged.connect(self._validate)
        self.asset_list.itemChanged.connect(self._validate)
        self._validate()

    def _validate(self) -> None:
        """Update save readiness and provide actionable validation explanations."""
        issues = self._collect_validation_explanations()
        self.validation_explanations = issues
        blocking = tuple(issue for issue in issues if issue.severity is ValidationSeverity.ERROR)
        self.save_button.setEnabled(not blocking)
        self.validation_label.setText(self._validation_html(issues))
        self.validation_label.setStyleSheet(
            "color: #b00020;" if blocking else "color: #6b5200;" if issues else ""
        )

    def _collect_validation_explanations(self) -> tuple[ValidationExplanation, ...]:
        issues: list[ValidationExplanation] = []
        self._require(
            issues,
            bool(self.scene_name_edit.text().strip()),
            "Scene name",
            "Enter a short, recognisable scene name.",
            ("The Story Browser and production team use it to identify the scene quickly."),
            "scene.name",
            self.scene_name_edit,
        )
        self._require(
            issues,
            bool(self.episode_id_edit.text().strip()),
            "Container ID",
            "Enter the canonical production container ID.",
            ("Every scene must belong to an episode, trailer, teaser, promo, test or special."),
            "scene.container_id",
            self.episode_id_edit,
        )
        container_id = self.episode_id_edit.text().strip()
        if container_id and not self._CONTAINER_PATTERN.fullmatch(container_id.upper()):
            issues.append(
                ValidationExplanation(
                    field_name="Container ID",
                    message="Use letters, numbers and single hyphens only.",
                    reason=(
                        "A canonical container ID is required to generate stable scene, "
                        "shot, ACPP and render identities."
                    ),
                    topic_id="scene.container_id",
                    widget=self.episode_id_edit,
                )
            )
        self._require(
            issues,
            bool(self.heading_edit.text().strip()),
            "Heading",
            "Enter a screenplay-style scene heading.",
            ("SSIE uses the heading to understand setting, interior/exterior context and time."),
            "scene.heading",
            self.heading_edit,
        )
        self._require(
            issues,
            bool(self.selected_location_id()),
            "Primary location",
            "Select one canonical Location or Environment asset.",
            ("A primary location anchors continuity, staging, lighting and required assets."),
            "scene.location",
            self.location_combo,
        )
        self._require(
            issues,
            bool(self.summary_edit.toPlainText().strip()),
            "Scene summary",
            "Describe the story event and what changes in the scene.",
            "SSIE needs the dramatic purpose to generate meaningful shot coverage.",
            "scene.summary",
            self.summary_edit,
        )
        issues.extend(self._unavailable_reference_warnings())
        return tuple(issues)

    @staticmethod
    def _require(
        issues: list[ValidationExplanation],
        condition: bool,
        field_name: str,
        message: str,
        reason: str,
        topic_id: str,
        widget: QWidget,
    ) -> None:
        if condition:
            return
        issues.append(
            ValidationExplanation(
                field_name=field_name,
                message=message,
                reason=reason,
                topic_id=topic_id,
                widget=widget,
            )
        )

    def _unavailable_reference_warnings(self) -> tuple[ValidationExplanation, ...]:
        warnings: list[ValidationExplanation] = []
        location_text = self.location_combo.currentText()
        if location_text.startswith("Unavailable asset"):
            warnings.append(
                self._reference_warning(
                    "Primary location",
                    "Restore the missing location or select another canonical location.",
                    "scene.location",
                    self.location_combo,
                )
            )
        if self._contains_unavailable_item(self.participant_list):
            warnings.append(
                self._reference_warning(
                    "Participants",
                    "One or more referenced characters are missing from Asset Manager.",
                    "scene.participants",
                    self.participant_list,
                )
            )
        if self._contains_unavailable_item(self.asset_list):
            warnings.append(
                self._reference_warning(
                    "Required assets",
                    ("One or more referenced production assets are missing from Asset Manager."),
                    "scene.required_assets",
                    self.asset_list,
                )
            )
        return tuple(warnings)

    @staticmethod
    def _contains_unavailable_item(widget: QListWidget) -> bool:
        return any(
            widget.item(index).text().startswith("Unavailable") for index in range(widget.count())
        )

    @staticmethod
    def _reference_warning(
        field_name: str,
        message: str,
        topic_id: str,
        widget: QWidget,
    ) -> ValidationExplanation:
        return ValidationExplanation(
            field_name=field_name,
            message=message,
            reason=(
                "The reference is preserved to prevent data loss, but production cannot "
                "resolve it until the canonical asset is restored or replaced."
            ),
            topic_id=topic_id,
            widget=widget,
            severity=ValidationSeverity.WARNING,
        )

    @staticmethod
    def _validation_html(issues: tuple[ValidationExplanation, ...]) -> str:
        if not issues:
            return (
                "<b>Ready to save.</b> All required scene information is complete and "
                "the production identity is valid."
            )
        errors = sum(issue.severity is ValidationSeverity.ERROR for issue in issues)
        heading = (
            (f"<b>{errors} issue{'s' if errors != 1 else ''} must be resolved before saving.</b>")
            if errors
            else "<b>Scene can be saved, but review these production warnings.</b>"
        )
        rows = "".join(
            f"<li><b>{issue.field_name}:</b> {issue.message} <span>{issue.reason}</span></li>"
            for issue in issues
        )
        return f"{heading}<ul>{rows}</ul>"

    def _focus_first_invalid_field(self) -> None:
        blocking = next(
            (
                issue
                for issue in self.validation_explanations
                if issue.severity is ValidationSeverity.ERROR
            ),
            None,
        )
        if blocking is None:
            return
        blocking.widget.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.scroll_area.ensureWidgetVisible(blocking.widget, 16, 16)
        self.show_live_topic(blocking.topic_id)
