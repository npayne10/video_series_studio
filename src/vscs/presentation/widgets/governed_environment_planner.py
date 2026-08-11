"""Authoritative Environment Planner UI for Phase 19.3.7."""

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
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vscs.application.story import (
    AtmosphereState,
    EnvironmentContext,
    EnvironmentPlan,
    EnvironmentPlanStatus,
    GovernedEnvironmentPlanningError,
    GovernedEnvironmentPlanningService,
    ShotPlan,
    TimeContext,
    WeatherState,
)


@dataclass(frozen=True, slots=True)
class EnvironmentEditorValues:
    environment_context: EnvironmentContext
    time_context: TimeContext
    atmosphere_state: AtmosphereState
    weather_state: WeatherState
    gravity_m_s2: float | None
    pressure_kpa: float | None
    temperature_c: float | None
    visibility_m: float | None
    surface_state: str
    environmental_motion: str
    hazard_notes: str
    continuity_notes: str
    environment_constraints: tuple[str, ...]


class EnvironmentPlanEditorDialog(QDialog):
    """Resizable scrollable editor for production-relevant environment state only."""

    def __init__(
        self,
        service: GovernedEnvironmentPlanningService,
        shot: ShotPlan,
        plan: EnvironmentPlan | None = None,
        *,
        suggested: EnvironmentPlan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        source = plan or suggested
        self.setObjectName("environmentPlanEditorDialog")
        self.setWindowTitle("Edit Environment Plan" if plan else "New Environment Plan")
        self.setMinimumSize(680, 520)
        self.resize(840, 740)

        body = QWidget(self)
        form = QFormLayout(body)
        shot_label = QLabel(f"{shot.shot_id} — {shot.title}", body)
        shot_label.setWordWrap(True)
        form.addRow("Governed Shot", shot_label)
        setting_label = QLabel(service.setting_requirement(shot.shot_id) or "—", body)
        setting_label.setWordWrap(True)
        form.addRow("Scene setting requirement", setting_label)

        self.context_combo = self._enum_combo(EnvironmentContext, body)
        self.time_combo = self._enum_combo(TimeContext, body)
        self.atmosphere_combo = self._enum_combo(AtmosphereState, body)
        self.weather_combo = self._enum_combo(WeatherState, body)
        self.gravity_edit = QLineEdit(body)
        self.gravity_edit.setPlaceholderText("Unknown / not established")
        self.pressure_edit = QLineEdit(body)
        self.pressure_edit.setPlaceholderText("Unknown / not established")
        self.temperature_edit = QLineEdit(body)
        self.temperature_edit.setPlaceholderText("Unknown / not established")
        self.visibility_edit = QLineEdit(body)
        self.visibility_edit.setPlaceholderText("Unknown / not established")
        self.surface_edit = QPlainTextEdit(body)
        self.motion_edit = QPlainTextEdit(body)
        self.hazard_edit = QPlainTextEdit(body)
        self.continuity_edit = QPlainTextEdit(body)
        self.constraints_edit = QPlainTextEdit(body)

        form.addRow("Environment context", self.context_combo)
        form.addRow("Time context", self.time_combo)
        form.addRow("Atmosphere state", self.atmosphere_combo)
        form.addRow("Weather state", self.weather_combo)
        form.addRow("Gravity (m/s²)", self.gravity_edit)
        form.addRow("Pressure (kPa)", self.pressure_edit)
        form.addRow("Temperature (°C)", self.temperature_edit)
        form.addRow("Visibility (m)", self.visibility_edit)
        form.addRow("Surface / environment state *", self.surface_edit)
        form.addRow("Environmental motion *", self.motion_edit)
        form.addRow("Environmental hazards", self.hazard_edit)
        form.addRow("Environment continuity notes", self.continuity_edit)
        form.addRow("Environment-specific constraints", self.constraints_edit)

        if source is not None:
            self._load(source)

        unknown_note = QLabel(
            "Leave physical values blank when canon has not established them. VSCS should preserve unknown physics rather than invent gravity, pressure, temperature or visibility.",
            body,
        )
        unknown_note.setWordWrap(True)
        form.addRow("Grounded-realism rule", unknown_note)
        scope = QLabel(
            "Camera framing, lighting design/exposure, asset authoring, prompts and renderer settings are owned elsewhere.",
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

    @staticmethod
    def _optional_text(value: float | None) -> str:
        return "" if value is None else f"{value:g}"

    @staticmethod
    def _optional_number(editor: QLineEdit, label: str) -> float | None:
        text = editor.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{label} must be a number or left blank") from exc

    def _load(self, plan: EnvironmentPlan) -> None:
        self._set_combo(self.context_combo, plan.environment_context.value)
        self._set_combo(self.time_combo, plan.time_context.value)
        self._set_combo(self.atmosphere_combo, plan.atmosphere_state.value)
        self._set_combo(self.weather_combo, plan.weather_state.value)
        self.gravity_edit.setText(self._optional_text(plan.gravity_m_s2))
        self.pressure_edit.setText(self._optional_text(plan.pressure_kpa))
        self.temperature_edit.setText(self._optional_text(plan.temperature_c))
        self.visibility_edit.setText(self._optional_text(plan.visibility_m))
        self.surface_edit.setPlainText(plan.surface_state)
        self.motion_edit.setPlainText(plan.environmental_motion)
        self.hazard_edit.setPlainText(plan.hazard_notes)
        self.continuity_edit.setPlainText(plan.continuity_notes)
        self.constraints_edit.setPlainText("\n".join(plan.environment_constraints))

    def _accept_if_valid(self) -> None:
        if not self.surface_edit.toPlainText().strip():
            QMessageBox.warning(
                self, "Environment Planner", "Surface / environment state is required."
            )
            return
        if not self.motion_edit.toPlainText().strip():
            QMessageBox.warning(
                self, "Environment Planner", "Environmental motion is required."
            )
            return
        try:
            self.values()
        except ValueError as exc:
            QMessageBox.warning(self, "Environment Planner", str(exc))
            return
        self.accept()

    def values(self) -> EnvironmentEditorValues:
        return EnvironmentEditorValues(
            environment_context=EnvironmentContext(str(self.context_combo.currentData())),
            time_context=TimeContext(str(self.time_combo.currentData())),
            atmosphere_state=AtmosphereState(str(self.atmosphere_combo.currentData())),
            weather_state=WeatherState(str(self.weather_combo.currentData())),
            gravity_m_s2=self._optional_number(self.gravity_edit, "Gravity"),
            pressure_kpa=self._optional_number(self.pressure_edit, "Pressure"),
            temperature_c=self._optional_number(self.temperature_edit, "Temperature"),
            visibility_m=self._optional_number(self.visibility_edit, "Visibility"),
            surface_state=self.surface_edit.toPlainText().strip(),
            environmental_motion=self.motion_edit.toPlainText().strip(),
            hazard_notes=self.hazard_edit.toPlainText().strip(),
            continuity_notes=self.continuity_edit.toPlainText().strip(),
            environment_constraints=tuple(
                line.strip()
                for line in self.constraints_edit.toPlainText().splitlines()
                if line.strip()
            ),
        )


class GovernedEnvironmentPlannerDialog(QDialog):
    """Manage the single authoritative Environment Plan beneath one governed Lighting Plan."""

    def __init__(
        self,
        service: GovernedEnvironmentPlanningService,
        shot: ShotPlan,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.shot_id = shot.shot_id
        self.setObjectName("governedEnvironmentPlannerDialog")
        self.setWindowTitle(f"Environment Planner — {shot.shot_id} — {shot.title}")
        self.setMinimumSize(780, 500)
        self.resize(1000, 660)

        root = QVBoxLayout(self)
        self.upstream_label = QLabel(self)
        self.upstream_label.setWordWrap(True)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("environmentPlannerStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.upstream_label)
        root.addWidget(self.status_label)

        guidance = QLabel(
            "Environment Planner owns physical world state: setting context, time context, atmosphere, weather, physical conditions, surface state, environmental motion and hazards. It consumes the governed Lighting Plan without redefining lighting.",
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
        self.details.setObjectName("environmentPlannerDetails")
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

    @staticmethod
    def _physical_value(value: float | None, suffix: str) -> str:
        return "Unknown" if value is None else f"{value:g} {suffix}"

    def refresh(self) -> None:
        shot = self.service.shots.plan(self.shot_id)
        shot_ready = shot is not None and self.service.shots.is_production_ready(shot)
        assets_ready = self.service.assets.shot_ready(self.shot_id) if shot_ready else False
        camera = self.service.camera.plan(self.shot_id) if shot_ready else None
        camera_ready = camera is not None and self.service.camera.is_production_ready(camera)
        lighting = self.service.lighting.plan(self.shot_id) if camera_ready else None
        lighting_ready = (
            lighting is not None and self.service.lighting.is_production_ready(lighting)
        )
        self.upstream_label.setText(
            f"Shot: {'Ready/current' if shot_ready else 'not production-ready'} • "
            f"Assets: {'Ready/current' if assets_ready else 'incomplete or stale'} • "
            f"Camera: {'Ready/current' if camera_ready else 'incomplete or stale'} • "
            f"Lighting: {'Ready/current' if lighting_ready else 'incomplete or stale'}"
        )
        plan = self.service.plan(self.shot_id)
        if plan is None:
            self.status_label.setText("No governed Environment Plan exists for this Shot.")
            self.details.setText(
                "Create a deterministic suggested Draft or a blank Draft. Unknown physical values remain explicitly unknown rather than being fabricated."
            )
        else:
            governance = plan.status.value.title()
            if plan.status is EnvironmentPlanStatus.READY and not self.service.is_production_ready(
                plan
            ):
                governance += " / Stale"
            self.status_label.setText(
                f"{plan.environment_plan_id} • {governance} • "
                + " • ".join(self.service.readiness_summary(self.shot_id))
            )
            self.details.setText(
                f"Context: {plan.environment_context.value.replace('_', ' ').title()}\n"
                f"Time context: {plan.time_context.value.replace('_', ' ').title()}\n"
                f"Atmosphere: {plan.atmosphere_state.value.replace('_', ' ').title()}\n"
                f"Weather: {plan.weather_state.value.replace('_', ' ').title()}\n"
                f"Gravity: {self._physical_value(plan.gravity_m_s2, 'm/s²')}\n"
                f"Pressure: {self._physical_value(plan.pressure_kpa, 'kPa')}\n"
                f"Temperature: {self._physical_value(plan.temperature_c, '°C')}\n"
                f"Visibility: {self._physical_value(plan.visibility_m, 'm')}\n\n"
                f"Surface/environment state: {plan.surface_state}\n\n"
                f"Environmental motion: {plan.environmental_motion}\n\n"
                f"Hazards: {plan.hazard_notes or '—'}\n\n"
                f"Continuity: {plan.continuity_notes or '—'}"
            )
        draft = plan is not None and plan.status is EnvironmentPlanStatus.DRAFT
        ready = plan is not None and plan.status is EnvironmentPlanStatus.READY
        can_plan = shot_ready and assets_ready and camera_ready and lighting_ready
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
        except GovernedEnvironmentPlanningError as exc:
            QMessageBox.warning(self, "Environment Planner", str(exc))
        self.refresh()

    def _create_blank(self) -> None:
        shot = self._shot()
        if shot is None:
            return
        suggested = self.service.suggested_plan(self.shot_id)
        dialog = EnvironmentPlanEditorDialog(
            self.service, shot, suggested=suggested, parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.create(shot_id=self.shot_id, **asdict(values))
        except (GovernedEnvironmentPlanningError, TypeError) as exc:
            QMessageBox.warning(self, "Environment Planner", str(exc))
        self.refresh()

    def _edit(self) -> None:
        shot = self._shot()
        plan = self.service.plan(self.shot_id)
        if shot is None or plan is None or plan.status is not EnvironmentPlanStatus.DRAFT:
            return
        dialog = EnvironmentPlanEditorDialog(self.service, shot, plan, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.update(self.shot_id, **asdict(values))
        except (GovernedEnvironmentPlanningError, TypeError) as exc:
            QMessageBox.warning(self, "Environment Planner", str(exc))
        self.refresh()

    def _mark_ready(self) -> None:
        try:
            self.service.mark_ready(self.shot_id)
        except GovernedEnvironmentPlanningError as exc:
            QMessageBox.warning(self, "Environment Planner", str(exc))
        self.refresh()

    def _return_to_draft(self) -> None:
        try:
            self.service.return_to_draft(self.shot_id)
        except GovernedEnvironmentPlanningError as exc:
            QMessageBox.warning(self, "Environment Planner", str(exc))
        self.refresh()

    def _delete(self) -> None:
        answer = QMessageBox.question(
            self,
            "Delete Environment Plan",
            f"Delete the Draft Environment Plan for {self.shot_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(self.shot_id)
        except GovernedEnvironmentPlanningError as exc:
            QMessageBox.warning(self, "Environment Planner", str(exc))
        self.refresh()
