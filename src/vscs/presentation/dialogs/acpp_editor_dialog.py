"""Editable Advanced Clip Production Package workspace."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vscs.application.acpp import (
    ACPPEditorError,
    ACPPEditorService,
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipProductionPackage,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    RenderQualityMode,
    RenderSpecification,
    SeedPolicy,
)
from vscs.application.shots import ProductionShot


class ACPPEditorDialog(QDialog):
    """Create and edit one versioned ACPP associated with a production shot."""

    def __init__(
        self,
        shot: ProductionShot,
        service: ACPPEditorService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.shot = shot
        self.service = service
        self.package = service.package_for_shot(shot.shot_id) or service.create_from_shot(shot)
        self.setWindowTitle(f"ACPP Editor — {shot.shot_id}")
        self.resize(1180, 820)
        self.setMinimumSize(900, 640)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("acppEditorTabs")
        self._build_identity_tab()
        self._build_prompt_tab()
        self._build_assets_tab()
        self._build_continuity_audio_tab()
        self._build_render_output_tab()

        self.validation_label = QLabel(self)
        self.validation_label.setWordWrap(True)
        self.version_label = QLabel(self)
        self.save_button = QPushButton("Save ACPP", self)
        self.validate_button = QPushButton("Validate", self)
        self.history_button = QPushButton("Version History", self)

        actions = QHBoxLayout()
        actions.addWidget(self.version_label)
        actions.addStretch(1)
        actions.addWidget(self.history_button)
        actions.addWidget(self.validate_button)
        actions.addWidget(self.save_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.validation_label)
        layout.addLayout(actions)
        layout.addWidget(buttons)

        self.save_button.clicked.connect(self._save)
        self.validate_button.clicked.connect(self._validate)
        self.history_button.clicked.connect(self._show_history)
        self._load(self.package)
        self._validate()

    @staticmethod
    def _scroll_form() -> tuple[QScrollArea, QFormLayout]:
        content = QWidget()
        form = QFormLayout(content)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll, form

    def _build_identity_tab(self) -> None:
        scroll, form = self._scroll_form()
        self.clip_id_edit = QLineEdit()
        self.clip_id_edit.setReadOnly(True)
        self.production_id_edit = QLineEdit()
        self.episode_id_edit = QLineEdit()
        self.scene_id_edit = QLineEdit()
        self.scene_id_edit.setReadOnly(True)
        self.shot_id_edit = QLineEdit()
        self.shot_id_edit.setReadOnly(True)
        self.status_combo = QComboBox()
        self.status_combo.addItems(("draft", "ready", "approved"))
        form.addRow("Clip ID", self.clip_id_edit)
        form.addRow("Production ID", self.production_id_edit)
        form.addRow("Container ID", self.episode_id_edit)
        form.addRow("Scene ID", self.scene_id_edit)
        form.addRow("Shot ID", self.shot_id_edit)
        form.addRow("Editor status", self.status_combo)
        self.tabs.addTab(scroll, "Identity")

    def _build_prompt_tab(self) -> None:
        scroll, form = self._scroll_form()
        self.visual_edit = QPlainTextEdit()
        self.negative_edit = QPlainTextEdit()
        self.camera_edit = QPlainTextEdit()
        self.lighting_edit = QPlainTextEdit()
        self.behaviour_edit = QPlainTextEdit()
        self.environment_edit = QPlainTextEdit()
        self.continuity_prompt_edit = QPlainTextEdit()
        form.addRow("Positive visual intent *", self.visual_edit)
        form.addRow("Negative constraints", self.negative_edit)
        form.addRow("Camera language", self.camera_edit)
        form.addRow("Lighting intent", self.lighting_edit)
        form.addRow("Behaviour and blocking", self.behaviour_edit)
        form.addRow("Environment intent", self.environment_edit)
        form.addRow("Continuity intent", self.continuity_prompt_edit)
        self.tabs.addTab(scroll, "Prompt")

    def _build_assets_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.asset_list = QListWidget()
        self.asset_id_edit = QLineEdit()
        self.asset_role_combo = QComboBox()
        for role in AssetBindingRole:
            self.asset_role_combo.addItem(role.value.title(), role.value)
        self.add_asset_button = QPushButton("Add Asset")
        self.remove_asset_button = QPushButton("Remove Selected")
        row = QHBoxLayout()
        row.addWidget(QLabel("Asset ID"))
        row.addWidget(self.asset_id_edit, 1)
        row.addWidget(self.asset_role_combo)
        row.addWidget(self.add_asset_button)
        row.addWidget(self.remove_asset_button)
        layout.addWidget(self.asset_list, 1)
        layout.addLayout(row)
        self.add_asset_button.clicked.connect(self._add_asset)
        self.remove_asset_button.clicked.connect(self._remove_asset)
        self.tabs.addTab(page, "Assets")

    def _build_continuity_audio_tab(self) -> None:
        scroll, form = self._scroll_form()
        self.incoming_clip_edit = QLineEdit()
        self.start_reference_edit = QLineEdit()
        self.end_reference_edit = QLineEdit()
        self.requirements_edit = QPlainTextEdit()
        self.outgoing_edit = QPlainTextEdit()
        self.dialogue_edit = QPlainTextEdit()
        self.voice_profiles_edit = QPlainTextEdit()
        self.ambience_edit = QLineEdit()
        self.music_edit = QLineEdit()
        self.effects_edit = QPlainTextEdit()
        form.addRow("Incoming clip", self.incoming_clip_edit)
        form.addRow("Start reference", self.start_reference_edit)
        form.addRow("End reference", self.end_reference_edit)
        form.addRow("Continuity requirements", self.requirements_edit)
        form.addRow("Outgoing state", self.outgoing_edit)
        form.addRow("Dialogue", self.dialogue_edit)
        form.addRow("Voice profile IDs", self.voice_profiles_edit)
        form.addRow("Ambience profile", self.ambience_edit)
        form.addRow("Music cue", self.music_edit)
        form.addRow("Sound effect IDs", self.effects_edit)
        self.tabs.addTab(scroll, "Continuity & Audio")

    def _build_render_output_tab(self) -> None:
        scroll, form = self._scroll_form()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(64, 16384)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(64, 16384)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 240)
        self.frames_spin = QSpinBox()
        self.frames_spin.setRange(1, 1000000)
        self.quality_combo = QComboBox()
        for value in RenderQualityMode:
            self.quality_combo.addItem(value.value.title(), value.value)
        self.seed_combo = QComboBox()
        for value in SeedPolicy:
            self.seed_combo.addItem(value.value.title(), value.value)
        self.fixed_seed_edit = QLineEdit()
        self.output_directory_edit = QLineEdit()
        self.filename_edit = QLineEdit()
        self.container_edit = QLineEdit()
        form.addRow("Width", self.width_spin)
        form.addRow("Height", self.height_spin)
        form.addRow("Frames per second", self.fps_spin)
        form.addRow("Frame count", self.frames_spin)
        form.addRow("Quality", self.quality_combo)
        form.addRow("Seed policy", self.seed_combo)
        form.addRow("Fixed seed", self.fixed_seed_edit)
        form.addRow("Output directory", self.output_directory_edit)
        form.addRow("Filename stem *", self.filename_edit)
        form.addRow("Container", self.container_edit)
        self.tabs.addTab(scroll, "Render & Output")

    @staticmethod
    def _lines(edit: QPlainTextEdit) -> tuple[str, ...]:
        return tuple(
            line.strip()
            for line in edit.toPlainText().splitlines()
            if line.strip()
        )

    @staticmethod
    def _optional(edit: QLineEdit) -> str | None:
        value = edit.text().strip()
        return value or None

    def _load(self, package: ClipProductionPackage) -> None:
        identity = package.identity
        self.clip_id_edit.setText(identity.clip_id)
        self.production_id_edit.setText(identity.production_id)
        self.episode_id_edit.setText(identity.episode_id)
        self.scene_id_edit.setText(identity.scene_id)
        self.shot_id_edit.setText(identity.shot_id)
        self.status_combo.setCurrentText(
            package.metadata.get("editor_status", "draft")
        )
        prompt = package.prompt
        self.visual_edit.setPlainText(prompt.positive_visual_intent)
        self.negative_edit.setPlainText("\n".join(prompt.negative_constraints))
        self.camera_edit.setPlainText(prompt.camera_language)
        self.lighting_edit.setPlainText(prompt.lighting_intent)
        self.behaviour_edit.setPlainText(prompt.behaviour_intent)
        self.environment_edit.setPlainText(prompt.environment_intent)
        self.continuity_prompt_edit.setPlainText(prompt.continuity_intent)
        self.asset_list.clear()
        for asset in package.assets:
            self._append_asset(asset)
        continuity = package.continuity
        self.incoming_clip_edit.setText(continuity.incoming_clip_id or "")
        self.start_reference_edit.setText(continuity.start_reference_id or "")
        self.end_reference_edit.setText(continuity.end_reference_id or "")
        self.requirements_edit.setPlainText("\n".join(continuity.requirements))
        self.outgoing_edit.setPlainText("\n".join(continuity.outgoing_state))
        audio = package.audio
        self.dialogue_edit.setPlainText("\n".join(audio.dialogue_lines))
        self.voice_profiles_edit.setPlainText("\n".join(audio.voice_profile_ids))
        self.ambience_edit.setText(audio.ambience_profile_id or "")
        self.music_edit.setText(audio.music_cue_id or "")
        self.effects_edit.setPlainText("\n".join(audio.sound_effect_ids))
        render = package.render
        self.width_spin.setValue(render.width)
        self.height_spin.setValue(render.height)
        self.fps_spin.setValue(render.frames_per_second)
        self.frames_spin.setValue(render.frame_count)
        self.quality_combo.setCurrentText(render.quality_mode.value.title())
        self.seed_combo.setCurrentText(render.seed_policy.value.title())
        self.fixed_seed_edit.setText(
            "" if render.fixed_seed is None else str(render.fixed_seed)
        )
        self.output_directory_edit.setText(package.output.relative_directory)
        self.filename_edit.setText(package.output.filename_stem)
        self.container_edit.setText(package.output.container)
        self.version_label.setText(
            f"Version {package.metadata.get('editor_version', '1')}"
        )

    def _append_asset(self, binding: AssetBinding) -> None:
        item = f"{binding.role.value}: {binding.asset_id}"
        self.asset_list.addItem(item)

    def _asset_bindings(self) -> tuple[AssetBinding, ...]:
        result = []
        for index in range(self.asset_list.count()):
            role, asset_id = self.asset_list.item(index).text().split(": ", 1)
            result.append(
                AssetBinding(
                    asset_id=asset_id,
                    role=AssetBindingRole(role),
                )
            )
        return tuple(result)

    def _add_asset(self) -> None:
        asset_id = self.asset_id_edit.text().strip()
        if not asset_id:
            return
        self._append_asset(
            AssetBinding(
                asset_id=asset_id,
                role=AssetBindingRole(
                    str(self.asset_role_combo.currentData())
                ),
            )
        )
        self.asset_id_edit.clear()

    def _remove_asset(self) -> None:
        row = self.asset_list.currentRow()
        if row >= 0:
            self.asset_list.takeItem(row)

    def package_from_form(self) -> ClipProductionPackage:
        metadata = dict(self.package.metadata)
        metadata["editor_status"] = self.status_combo.currentText()
        fixed_seed = self.fixed_seed_edit.text().strip()
        return replace(
            self.package,
            identity=replace(
                self.package.identity,
                production_id=self.production_id_edit.text().strip(),
                episode_id=self.episode_id_edit.text().strip(),
            ),
            render=RenderSpecification(
                width=self.width_spin.value(),
                height=self.height_spin.value(),
                frames_per_second=self.fps_spin.value(),
                frame_count=self.frames_spin.value(),
                quality_mode=RenderQualityMode(
                    str(self.quality_combo.currentData())
                ),
                seed_policy=SeedPolicy(str(self.seed_combo.currentData())),
                fixed_seed=int(fixed_seed) if fixed_seed else None,
            ),
            assets=self._asset_bindings(),
            prompt=PromptSpecification(
                positive_visual_intent=(
                    self.visual_edit.toPlainText().strip()
                ),
                negative_constraints=self._lines(self.negative_edit),
                camera_language=self.camera_edit.toPlainText().strip(),
                lighting_intent=self.lighting_edit.toPlainText().strip(),
                behaviour_intent=self.behaviour_edit.toPlainText().strip(),
                environment_intent=self.environment_edit.toPlainText().strip(),
                continuity_intent=(
                    self.continuity_prompt_edit.toPlainText().strip()
                ),
            ),
            continuity=ContinuityBinding(
                incoming_clip_id=self._optional(self.incoming_clip_edit),
                start_reference_id=self._optional(self.start_reference_edit),
                end_reference_id=self._optional(self.end_reference_edit),
                requirements=self._lines(self.requirements_edit),
                outgoing_state=self._lines(self.outgoing_edit),
            ),
            audio=AudioSpecification(
                dialogue_lines=self._lines(self.dialogue_edit),
                voice_profile_ids=self._lines(self.voice_profiles_edit),
                ambience_profile_id=self._optional(self.ambience_edit),
                music_cue_id=self._optional(self.music_edit),
                sound_effect_ids=self._lines(self.effects_edit),
            ),
            output=OutputSpecification(
                relative_directory=(
                    self.output_directory_edit.text().strip()
                ),
                filename_stem=self.filename_edit.text().strip(),
                container=self.container_edit.text().strip() or "mp4",
            ),
            metadata=metadata,
        )

    def _validate(self) -> bool:
        try:
            package = self.package_from_form()
        except ValueError as exc:
            self.validation_label.setText(str(exc))
            self.save_button.setEnabled(False)
            return False
        result = self.service.validate(package)
        messages = [
            f"{issue.code}: {issue.message}" for issue in result.issues
        ]
        validation_text = (
            "Validation passed" if result.passed else " · ".join(messages)
        )
        self.validation_label.setText(validation_text)
        can_save = bool(
            package.prompt.positive_visual_intent
            and package.output.filename_stem
        )
        self.save_button.setEnabled(can_save)
        return result.passed

    def _save(self) -> None:
        try:
            stored = self.service.save(self.package_from_form())
        except (ACPPEditorError, ValueError) as exc:
            QMessageBox.warning(self, "ACPP Save", str(exc))
            return
        self.package = stored
        self._load(stored)
        self._validate()

    def _show_history(self) -> None:
        versions = self.service.versions(self.package.identity.clip_id)
        text = (
            "\n".join(
                f"Version {item.metadata.get('editor_version', '?')} — "
                f"{item.metadata.get('editor_status', 'draft')}"
                for item in versions
            )
            or "No saved versions yet."
        )
        QMessageBox.information(self, "ACPP Version History", text)
