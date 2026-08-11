"""Authoritative Lighting Planner UI for Phase 19.3.6."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vscs.application.story import (
    ExposureIntent,
    GovernedLightingPlanningError,
    GovernedLightingPlanningService,
    KeyDirection,
    LightingIntent,
    LightingPlan,
    LightingPlanStatus,
    LightQuality,
    ShotPlan,
)


@dataclass(frozen=True, slots=True)
class LightingEditorValues:
    lighting_intent: LightingIntent
    key_direction: KeyDirection
    key_quality: LightQuality
    color_temperature_k: int
    fill_level_percent: int
    exposure_intent: ExposureIntent
    source_strategy: str
    shadow_strategy: str
    subject_readability: str
    separation_strategy: str
    continuity_notes: str
    lighting_constraints: tuple[str, ...]
    lighting_profile_asset_id: str


class LightingPlanEditorDialog(QDialog):
    """Resizable scrollable editor for production-relevant lighting intent only."""

    def __init__(
        self,
        service: GovernedLightingPlanningService,
        shot: ShotPlan,
        plan: LightingPlan | None = None,
        *,
        suggested: LightingPlan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        source = plan or suggested
        self.setObjectName("lightingPlanEditorDialog")
        self.setWindowTitle("Edit Lighting Plan" if plan else "New Lighting Plan")
        self.setMinimumSize(660, 520)
        self.resize(820, 720)

        body = QWidget(self)
        form = QFormLayout(body)
        shot_label = QLabel(f"{shot.shot_id} — {shot.title}", body)
        shot_label.setWordWrap(True)
        form.addRow("Governed Shot", shot_label)

        self.profile_combo = QComboBox(body)
        self.profile_combo.addItem("— Explicit lighting plan only —", "")
        for asset_id, name in service.available_lighting_profiles():
            self.profile_combo.addItem(f"{asset_id} — {name}", asset_id)
        if source is not None and source.lighting_profile_asset_id:
            index = self.profile_combo.findData(source.lighting_profile_asset_id)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        form.addRow("Lighting profile", self.profile_combo)

        self.intent_combo = self._enum_combo(LightingIntent, body)
        self.direction_combo = self._enum_combo(KeyDirection, body)
        self.quality_combo = self._enum_combo(LightQuality, body)
        self.exposure_combo = self._enum_combo(ExposureIntent, body)
        self.temperature_spin = QSpinBox(body)
        self.temperature_spin.setRange(1500, 20000)
        self.temperature_spin.setSuffix(" K")
        self.fill_spin = QSpinBox(body)
        self.fill_spin.setRange(0, 100)
        self.fill_spin.setSuffix(" %")
        self.source_edit = QPlainTextEdit(body)
        self.shadow_edit = QPlainTextEdit(body)
        self.readability_edit = QPlainTextEdit(body)
        self.separation_edit = QPlainTextEdit(body)
        self.continuity_edit = QPlainTextEdit(body)
        self.constraints_edit = QPlainTextEdit(body)

        form.addRow("Lighting intent", self.intent_combo)
        form.addRow("Key direction", self.direction_combo)
        form.addRow("Key quality", self.quality_combo)
        form.addRow("Colour temperature", self.temperature_spin)
        form.addRow("Fill level", self.fill_spin)
        form.addRow("Exposure intent", self.exposure_combo)
        form.addRow("Motivated source strategy *", self.source_edit)
        form.addRow("Shadow strategy *", self.shadow_edit)
        form.addRow("Subject readability *", self.readability_edit)
        form.addRow("Separation strategy", self.separation_edit)
        form.addRow("Lighting continuity notes", self.continuity_edit)
        form.addRow("Lighting-specific constraints", self.constraints_edit)

        if source is not None:
            self._load(source)
        else:
            self.temperature_spin.setValue(4300)
            self.fill_spin.setValue(40)

        scope = QLabel(
            "Environment/weather/time-of-day, camera planning, asset authoring, prompts and renderer settings are owned elsewhere.",
            body,
        )
        scope.setWordWrap(True)
        form.addRow("Ownership boundary", scope)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        root = QVBoxLayout(self)
        root.addWidget(scroll, 1)
        root.addWidget(buttons)

    @staticmethod
    def _enum_combo(enum_type: type[StrEnum], parent: QWidget) -> QComboBox:
        combo = QComboBox(parent)
        for value in enum_type:
            combo.addItem(str(value.value).replace("_", " ").title(), value.value)
        return combo

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load(self, plan: LightingPlan) -> None:
        self._set_combo(self.intent_combo, plan.lighting_intent.value)
        self._set_combo(self.direction_combo, plan.key_direction.value)
        self._set_combo(self.quality_combo, plan.key_quality.value)
        self._set_combo(self.exposure_combo, plan.exposure_intent.value)
        self.temperature_spin.setValue(plan.color_temperature_k)
        self.fill_spin.setValue(plan.fill_level_percent)
        self.source_edit.setPlainText(plan.source_strategy)
        self.shadow_edit.setPlainText(plan.shadow_strategy)
        self.readability_edit.setPlainText(plan.subject_readability)
        self.separation_edit.setPlainText(plan.separation_strategy)
        self.continuity_edit.setPlainText(plan.continuity_notes)
        self.constraints_edit.setPlainText("\n".join(plan.lighting_constraints))

    def _accept_if_valid(self) -> None:
        for editor, message in (
            (self.source_edit, "Motivated source strategy is required."),
            (self.shadow_edit, "Shadow strategy is required."),
            (self.readability_edit, "Subject readability is required."),
        ):
            if not editor.toPlainText().strip():
                QMessageBox.warning(self, "Lighting Planner", message)
                return
        self.accept()

    def values(self) -> LightingEditorValues:
        return LightingEditorValues(
            lighting_intent=LightingIntent(str(self.intent_combo.currentData())),
            key_direction=KeyDirection(str(self.direction_combo.currentData())),
            key_quality=LightQuality(str(self.quality_combo.currentData())),
            color_temperature_k=self.temperature_spin.value(),
            fill_level_percent=self.fill_spin.value(),
            exposure_intent=ExposureIntent(str(self.exposure_combo.currentData())),
            source_strategy=self.source_edit.toPlainText().strip(),
            shadow_strategy=self.shadow_edit.toPlainText().strip(),
            subject_readability=self.readability_edit.toPlainText().strip(),
            separation_strategy=self.separation_edit.toPlainText().strip(),
            continuity_notes=self.continuity_edit.toPlainText().strip(),
            lighting_constraints=tuple(
                line.strip()
                for line in self.constraints_edit.toPlainText().splitlines()
                if line.strip()
            ),
            lighting_profile_asset_id=str(self.profile_combo.currentData() or "").strip().upper(),
        )


class GovernedLightingPlannerDialog(QDialog):
    """Manage the single authoritative Lighting Plan beneath one governed Camera Plan."""

    def __init__(
        self,
        service: GovernedLightingPlanningService,
        shot: ShotPlan,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.shot_id = shot.shot_id
        self.setObjectName("governedLightingPlannerDialog")
        self.setWindowTitle(f"Lighting Planner — {shot.shot_id} — {shot.title}")
        self.setMinimumSize(760, 480)
        self.resize(980, 640)

        root = QVBoxLayout(self)
        self.upstream_label = QLabel(self)
        self.upstream_label.setWordWrap(True)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("lightingPlannerStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.upstream_label)
        root.addWidget(self.status_label)

        guidance = QLabel(
            "Lighting Planner owns motivated illumination, source direction/quality, colour temperature, fill, exposure intent, shadows and subject readability. Environment/weather and camera decisions remain in their specialist planners.",
            self,
        )
        guidance.setWordWrap(True)
        root.addWidget(guidance)

        toolbar = QHBoxLayout()
        self.suggest_button = QPushButton("Create Suggested Draft", self)
        self.new_button = QPushButton("Create Blank Draft", self)
        self.edit_button = QPushButton("Edit", self)
        self.ready_button = QPushButton("Mark Ready", self)
        self.draft_button = QPushButton("Return to Draft", self)
        self.delete_button = QPushButton("Delete Draft", self)
        for button in (
            self.suggest_button,
            self.new_button,
            self.edit_button,
            self.ready_button,
            self.draft_button,
            self.delete_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.details = QLabel(self)
        self.details.setObjectName("lightingPlannerDetails")
        self.details.setWordWrap(True)
        root.addWidget(self.details, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.suggest_button.clicked.connect(self._create_suggested)
        self.new_button.clicked.connect(self._create_blank)
        self.edit_button.clicked.connect(self._edit)
        self.ready_button.clicked.connect(self._mark_ready)
        self.draft_button.clicked.connect(self._return_to_draft)
        self.delete_button.clicked.connect(self._delete)
        self.refresh()

    def refresh(self) -> None:
        shot = self.service.shots.plan(self.shot_id)
        shot_ready = shot is not None and self.service.shots.is_production_ready(shot)
        assets_ready = self.service.assets.shot_ready(self.shot_id) if shot_ready else False
        camera = self.service.camera.plan(self.shot_id) if shot_ready else None
        camera_ready = camera is not None and self.service.camera.is_production_ready(camera)
        self.upstream_label.setText(
            f"Shot: {'Ready/current' if shot_ready else 'not production-ready'} • "
            f"Assets: {'Ready/current' if assets_ready else 'incomplete or stale'} • "
            f"Camera: {'Ready/current' if camera_ready else 'incomplete or stale'}"
        )
        plan = self.service.plan(self.shot_id)
        if plan is None:
            self.status_label.setText("No governed Lighting Plan exists for this Shot.")
            self.details.setText("Create a deterministic suggested Draft or a blank Draft.")
        else:
            governance = plan.status.value.title()
            if plan.status is LightingPlanStatus.READY and not self.service.is_production_ready(plan):
                governance += " / Stale"
            self.status_label.setText(
                f"{plan.lighting_plan_id} • {governance} • "
                + " • ".join(self.service.readiness_summary(self.shot_id))
            )
            self.details.setText(
                f"Intent: {plan.lighting_intent.value.replace('_', ' ').title()}\n"
                f"Key: {plan.key_direction.value.replace('_', ' ').title()} / {plan.key_quality.value.title()}\n"
                f"Colour temperature: {plan.color_temperature_k} K\n"
                f"Fill: {plan.fill_level_percent}%\n"
                f"Exposure intent: {plan.exposure_intent.value.replace('_', ' ').title()}\n"
                f"Lighting profile: {plan.lighting_profile_asset_id or 'Explicit plan only'}\n\n"
                f"Source strategy: {plan.source_strategy}\n\n"
                f"Shadow strategy: {plan.shadow_strategy}\n\n"
                f"Subject readability: {plan.subject_readability}\n\n"
                f"Separation: {plan.separation_strategy or '—'}\n\n"
                f"Continuity: {plan.continuity_notes or '—'}"
            )
        draft = plan is not None and plan.status is LightingPlanStatus.DRAFT
        ready = plan is not None and plan.status is LightingPlanStatus.READY
        can_plan = shot_ready and assets_ready and camera_ready
        self.suggest_button.setEnabled(can_plan and plan is None)
        self.new_button.setEnabled(can_plan and plan is None)
        self.edit_button.setEnabled(can_plan and draft)
        self.ready_button.setEnabled(can_plan and draft)
        self.draft_button.setEnabled(ready)
        self.delete_button.setEnabled(draft)

    def _shot(self) -> ShotPlan | None:
        return self.service.shots.plan(self.shot_id)

    def _create_suggested(self) -> None:
        try:
            self.service.create_suggested(self.shot_id)
        except GovernedLightingPlanningError as exc:
            QMessageBox.warning(self, "Lighting Planner", str(exc))
        self.refresh()

    def _create_blank(self) -> None:
        shot = self._shot()
        if shot is None:
            return
        suggested = self.service.suggested_plan(self.shot_id)
        dialog = LightingPlanEditorDialog(self.service, shot, suggested=suggested, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.create(shot_id=self.shot_id, **asdict(values))
        except (GovernedLightingPlanningError, TypeError) as exc:
            QMessageBox.warning(self, "Lighting Planner", str(exc))
        self.refresh()

    def _edit(self) -> None:
        shot = self._shot()
        plan = self.service.plan(self.shot_id)
        if shot is None or plan is None or plan.status is not LightingPlanStatus.DRAFT:
            return
        dialog = LightingPlanEditorDialog(self.service, shot, plan, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.update(self.shot_id, **asdict(values))
        except (GovernedLightingPlanningError, TypeError) as exc:
            QMessageBox.warning(self, "Lighting Planner", str(exc))
        self.refresh()

    def _mark_ready(self) -> None:
        try:
            self.service.mark_ready(self.shot_id)
        except GovernedLightingPlanningError as exc:
            QMessageBox.warning(self, "Lighting Planner", str(exc))
        self.refresh()

    def _return_to_draft(self) -> None:
        try:
            self.service.return_to_draft(self.shot_id)
        except GovernedLightingPlanningError as exc:
            QMessageBox.warning(self, "Lighting Planner", str(exc))
        self.refresh()

    def _delete(self) -> None:
        answer = QMessageBox.question(
            self,
            "Delete Lighting Plan",
            f"Delete the Draft Lighting Plan for {self.shot_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(self.shot_id)
        except GovernedLightingPlanningError as exc:
            QMessageBox.warning(self, "Lighting Planner", str(exc))
        self.refresh()
