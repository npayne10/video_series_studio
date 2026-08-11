"""Authoritative Camera Planner UI for Phase 19.3.5."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
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
    CameraAngle,
    CameraMovement,
    CameraPlan,
    CameraPlanStatus,
    GovernedCameraPlanningError,
    GovernedCameraPlanningService,
    LensFamily,
    ScreenDirection,
    ShotPlan,
    ShotSize,
)


@dataclass(frozen=True, slots=True)
class CameraEditorValues:
    shot_size: ShotSize
    angle: CameraAngle
    movement: CameraMovement
    lens_family: LensFamily
    focal_length_mm: int
    camera_height_m: float
    screen_direction: ScreenDirection
    composition: str
    focus_strategy: str
    movement_notes: str
    continuity_notes: str
    camera_constraints: tuple[str, ...]
    camera_profile_asset_id: str


class CameraPlanEditorDialog(QDialog):
    """Resizable scrollable editor for production-relevant camera intent only."""

    def __init__(
        self,
        service: GovernedCameraPlanningService,
        shot: ShotPlan,
        plan: CameraPlan | None = None,
        *,
        suggested: CameraPlan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        source = plan or suggested
        self.setObjectName("cameraPlanEditorDialog")
        self.setWindowTitle("Edit Camera Plan" if plan else "New Camera Plan")
        self.setMinimumSize(660, 520)
        self.resize(820, 720)

        body = QWidget(self)
        form = QFormLayout(body)
        shot_label = QLabel(f"{shot.shot_id} — {shot.title}", body)
        shot_label.setWordWrap(True)
        form.addRow("Governed Shot", shot_label)

        self.profile_combo = QComboBox(body)
        self.profile_combo.addItem("— Explicit camera plan only —", "")
        for asset_id, name in service.available_camera_profiles():
            self.profile_combo.addItem(f"{asset_id} — {name}", asset_id)
        if source is not None and source.camera_profile_asset_id:
            index = self.profile_combo.findData(source.camera_profile_asset_id)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        form.addRow("Camera profile", self.profile_combo)

        self.shot_size_combo = self._enum_combo(ShotSize, body)
        self.angle_combo = self._enum_combo(CameraAngle, body)
        self.movement_combo = self._enum_combo(CameraMovement, body)
        self.lens_combo = self._enum_combo(LensFamily, body)
        self.direction_combo = self._enum_combo(ScreenDirection, body)
        self.focal_spin = QSpinBox(body)
        self.focal_spin.setRange(8, 1200)
        self.focal_spin.setSuffix(" mm (full-frame eq.)")
        self.height_spin = QDoubleSpinBox(body)
        self.height_spin.setRange(0.05, 100.0)
        self.height_spin.setDecimals(2)
        self.height_spin.setSuffix(" m")
        self.composition_edit = QPlainTextEdit(body)
        self.focus_edit = QPlainTextEdit(body)
        self.movement_notes_edit = QPlainTextEdit(body)
        self.continuity_edit = QPlainTextEdit(body)
        self.constraints_edit = QPlainTextEdit(body)

        form.addRow("Shot size", self.shot_size_combo)
        form.addRow("Angle", self.angle_combo)
        form.addRow("Movement", self.movement_combo)
        form.addRow("Lens family", self.lens_combo)
        form.addRow("Focal length", self.focal_spin)
        form.addRow("Physical camera height", self.height_spin)
        form.addRow("Screen direction", self.direction_combo)
        form.addRow("Composition *", self.composition_edit)
        form.addRow("Focus strategy *", self.focus_edit)
        form.addRow("Movement / physical notes", self.movement_notes_edit)
        form.addRow("Continuity notes", self.continuity_edit)
        form.addRow("Camera-specific constraints", self.constraints_edit)

        if source is not None:
            self._load(source)
        else:
            self.focal_spin.setValue(50)
            self.height_spin.setValue(1.6)

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
    def _enum_combo(enum_type: type, parent: QWidget) -> QComboBox:
        combo = QComboBox(parent)
        for value in enum_type:
            combo.addItem(str(value.value).replace("_", " ").title(), value.value)
        return combo

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load(self, plan: CameraPlan) -> None:
        self._set_combo(self.shot_size_combo, plan.shot_size.value)
        self._set_combo(self.angle_combo, plan.angle.value)
        self._set_combo(self.movement_combo, plan.movement.value)
        self._set_combo(self.lens_combo, plan.lens_family.value)
        self._set_combo(self.direction_combo, plan.screen_direction.value)
        self.focal_spin.setValue(plan.focal_length_mm)
        self.height_spin.setValue(plan.camera_height_m)
        self.composition_edit.setPlainText(plan.composition)
        self.focus_edit.setPlainText(plan.focus_strategy)
        self.movement_notes_edit.setPlainText(plan.movement_notes)
        self.continuity_edit.setPlainText(plan.continuity_notes)
        self.constraints_edit.setPlainText("\n".join(plan.camera_constraints))

    def _accept_if_valid(self) -> None:
        if not self.composition_edit.toPlainText().strip():
            QMessageBox.warning(self, "Camera Planner", "Composition is required.")
            return
        if not self.focus_edit.toPlainText().strip():
            QMessageBox.warning(self, "Camera Planner", "Focus strategy is required.")
            return
        self.accept()

    def values(self) -> CameraEditorValues:
        return CameraEditorValues(
            shot_size=ShotSize(str(self.shot_size_combo.currentData())),
            angle=CameraAngle(str(self.angle_combo.currentData())),
            movement=CameraMovement(str(self.movement_combo.currentData())),
            lens_family=LensFamily(str(self.lens_combo.currentData())),
            focal_length_mm=self.focal_spin.value(),
            camera_height_m=self.height_spin.value(),
            screen_direction=ScreenDirection(str(self.direction_combo.currentData())),
            composition=self.composition_edit.toPlainText().strip(),
            focus_strategy=self.focus_edit.toPlainText().strip(),
            movement_notes=self.movement_notes_edit.toPlainText().strip(),
            continuity_notes=self.continuity_edit.toPlainText().strip(),
            camera_constraints=tuple(
                line.strip() for line in self.constraints_edit.toPlainText().splitlines() if line.strip()
            ),
            camera_profile_asset_id=str(self.profile_combo.currentData() or "").strip().upper(),
        )


class GovernedCameraPlannerDialog(QDialog):
    """Manage the single authoritative Camera Plan beneath one governed Shot."""

    def __init__(
        self,
        service: GovernedCameraPlanningService,
        shot: ShotPlan,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.shot_id = shot.shot_id
        self.setObjectName("governedCameraPlannerDialog")
        self.setWindowTitle(f"Camera Planner — {shot.shot_id} — {shot.title}")
        self.setMinimumSize(760, 480)
        self.resize(980, 640)

        root = QVBoxLayout(self)
        self.upstream_label = QLabel(self)
        self.upstream_label.setWordWrap(True)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("cameraPlannerStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.upstream_label)
        root.addWidget(self.status_label)

        guidance = QLabel(
            "Camera Planner owns framing, angle, movement, lens/focal length, screen direction, composition "
            "and focus intent. Lighting, environment and asset authoring remain in their specialist planners.",
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
        self.details.setObjectName("cameraPlannerDetails")
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(self.details.textInteractionFlags())
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
        self.upstream_label.setText(
            f"Upstream Shot: {'Ready/current' if shot_ready else 'not production-ready'} • "
            f"Asset context: {'Ready/current' if assets_ready else 'incomplete or stale'}"
        )
        plan = self.service.plan(self.shot_id)
        if plan is None:
            self.status_label.setText("No governed Camera Plan exists for this Shot.")
            self.details.setText("Create a deterministic suggested Draft or a blank Draft.")
        else:
            governance = plan.status.value.title()
            if plan.status is CameraPlanStatus.READY and not self.service.is_production_ready(plan):
                governance += " / Stale"
            self.status_label.setText(
                f"{plan.camera_plan_id} • {governance} • " + " • ".join(self.service.readiness_summary(self.shot_id))
            )
            self.details.setText(
                f"Shot size: {plan.shot_size.value.replace('_', ' ').title()}\n"
                f"Angle: {plan.angle.value.replace('_', ' ').title()}\n"
                f"Movement: {plan.movement.value.replace('_', ' ').title()}\n"
                f"Lens: {plan.lens_family.value.replace('_', ' ').title()} / {plan.focal_length_mm} mm\n"
                f"Camera height: {plan.camera_height_m:.2f} m\n"
                f"Screen direction: {plan.screen_direction.value.replace('_', ' ').title()}\n"
                f"Camera profile: {plan.camera_profile_asset_id or 'Explicit plan only'}\n\n"
                f"Composition: {plan.composition}\n\nFocus: {plan.focus_strategy}\n\n"
                f"Movement notes: {plan.movement_notes or '—'}\n\n"
                f"Continuity: {plan.continuity_notes or '—'}"
            )
        draft = plan is not None and plan.status is CameraPlanStatus.DRAFT
        ready = plan is not None and plan.status is CameraPlanStatus.READY
        self.suggest_button.setEnabled(shot_ready and plan is None)
        self.new_button.setEnabled(shot_ready and plan is None)
        self.edit_button.setEnabled(shot_ready and draft)
        self.ready_button.setEnabled(shot_ready and draft)
        self.draft_button.setEnabled(ready)
        self.delete_button.setEnabled(draft)

    def _shot(self) -> ShotPlan | None:
        return self.service.shots.plan(self.shot_id)

    def _create_suggested(self) -> None:
        try:
            self.service.create_suggested(self.shot_id)
        except GovernedCameraPlanningError as exc:
            QMessageBox.warning(self, "Camera Planner", str(exc))
        self.refresh()

    def _create_blank(self) -> None:
        shot = self._shot()
        if shot is None:
            return
        suggested = self.service.suggested_plan(self.shot_id)
        dialog = CameraPlanEditorDialog(self.service, shot, suggested=suggested, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.create(shot_id=self.shot_id, **values.__dict__)
        except (GovernedCameraPlanningError, TypeError) as exc:
            QMessageBox.warning(self, "Camera Planner", str(exc))
        self.refresh()

    def _edit(self) -> None:
        shot = self._shot()
        plan = self.service.plan(self.shot_id)
        if shot is None or plan is None or plan.status is not CameraPlanStatus.DRAFT:
            return
        dialog = CameraPlanEditorDialog(self.service, shot, plan, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.update(self.shot_id, **values.__dict__)
        except (GovernedCameraPlanningError, TypeError) as exc:
            QMessageBox.warning(self, "Camera Planner", str(exc))
        self.refresh()

    def _mark_ready(self) -> None:
        try:
            self.service.mark_ready(self.shot_id)
        except GovernedCameraPlanningError as exc:
            QMessageBox.warning(self, "Camera Planner", str(exc))
        self.refresh()

    def _return_to_draft(self) -> None:
        try:
            self.service.return_to_draft(self.shot_id)
        except GovernedCameraPlanningError as exc:
            QMessageBox.warning(self, "Camera Planner", str(exc))
        self.refresh()

    def _delete(self) -> None:
        answer = QMessageBox.question(
            self,
            "Delete Camera Plan",
            f"Delete the Draft Camera Plan for {self.shot_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(self.shot_id)
        except GovernedCameraPlanningError as exc:
            QMessageBox.warning(self, "Camera Planner", str(exc))
        self.refresh()
