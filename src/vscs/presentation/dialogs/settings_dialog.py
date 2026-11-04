"""Application settings dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vscs.infrastructure.ai import AICredentialStore, CredentialStorageError
from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider
from vscs.infrastructure.ai.provider import AIProviderError
from vscs.infrastructure.configuration import AIProvider, ConfigurationService, Theme


class _OpenAIModelDiscovery(QThread):
    """Run model listing without blocking the Settings UI."""

    models_loaded = Signal(tuple)
    models_failed = Signal(str)

    def __init__(self, api_key: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.api_key = api_key

    def run(self) -> None:
        try:
            models = OpenAICAPGenerationProvider.list_available_models(api_key=self.api_key)
        except (AIProviderError, RuntimeError, ValueError) as exc:
            self.models_failed.emit(str(exc))
        else:
            self.models_loaded.emit(models)


class SettingsDialog(QDialog):
    """Edit commonly used VSCS preferences."""

    def __init__(
        self,
        configuration: ConfigurationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.configuration = configuration
        self.credentials = AICredentialStore()
        self.setWindowTitle("VSCS Settings")
        self.setMinimumWidth(560)

        self.theme_combo = QComboBox()
        for theme in Theme:
            self.theme_combo.addItem(theme.value.title(), theme)
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(configuration.settings.theme))

        self.maximum_recent_spin = QSpinBox()
        self.maximum_recent_spin.setRange(1, 50)
        self.maximum_recent_spin.setValue(configuration.settings.maximum_recent_projects)

        self.restore_last_project = QCheckBox()
        self.restore_last_project.setChecked(configuration.settings.workspace.restore_last_project)

        self.confirm_before_exit = QCheckBox()
        self.confirm_before_exit.setChecked(configuration.settings.workspace.confirm_before_exit)

        self.media_output_directory = QLineEdit(
            configuration.settings.workspace.media_output_directory
        )
        self.media_output_directory.setPlaceholderText("Media Output")
        self.media_output_directory.setToolTip(
            "Project-relative folder used for authoritative Generated Media. "
            "The default is 'Media Output'."
        )

        general_form = QFormLayout()
        general_form.addRow("Theme", self.theme_combo)
        general_form.addRow("Maximum recent projects", self.maximum_recent_spin)
        general_form.addRow("Restore last project", self.restore_last_project)
        general_form.addRow("Confirm before exit", self.confirm_before_exit)
        general_form.addRow("Project media output folder", self.media_output_directory)
        general_group = QGroupBox("General")
        general_group.setLayout(general_form)

        comfyui = configuration.settings.renderers.get("comfyui")
        self.comfyui_output_directory = QLineEdit(
            str(comfyui.output_directory) if comfyui and comfyui.output_directory else ""
        )
        self.comfyui_output_directory.setPlaceholderText("Required for automatic media ingestion")
        self.comfyui_output_browse = QPushButton("Browse…")
        self.comfyui_output_browse.clicked.connect(self._browse_comfyui_output_directory)
        comfyui_output_row = QHBoxLayout()
        comfyui_output_row.addWidget(self.comfyui_output_directory, 1)
        comfyui_output_row.addWidget(self.comfyui_output_browse)

        renderer_note = QLabel(
            "VSCS copies completed provider files from this source folder into the current "
            "project's managed media output folder. Provider files are not moved or deleted."
        )
        renderer_note.setWordWrap(True)
        renderer_form = QFormLayout()
        renderer_form.addRow("ComfyUI output folder", comfyui_output_row)
        renderer_form.addRow("", renderer_note)
        renderer_group = QGroupBox("Production Renderer")
        renderer_group.setLayout(renderer_form)

        self.ai_provider = QComboBox()
        for provider in AIProvider:
            self.ai_provider.addItem(provider.value.title(), provider)
        self.ai_provider.setCurrentIndex(
            self.ai_provider.findData(configuration.settings.ai.provider)
        )

        self.openai_model = QComboBox()
        self.openai_model.setObjectName("openaiModelSelector")
        self.openai_model.setEditable(True)
        self.openai_model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.openai_model.addItem(configuration.settings.ai.openai_model)
        self.openai_model.setCurrentText(configuration.settings.ai.openai_model)
        self.openai_model.setToolTip(
            "Search or enter an exact API model ID. Refresh retrieves models visible "
            "to your key; not every model supports structured CAP generation."
        )
        self.refresh_openai_models_button = QPushButton("Refresh Models", self)
        self.refresh_openai_models_button.setObjectName("refreshOpenAIModels")
        self.refresh_openai_models_button.clicked.connect(self._refresh_openai_models)
        self.openai_model_status = QLabel(
            "Use Refresh Models to list API-visible models. Manual entry remains available."
        )
        self.openai_model_status.setWordWrap(True)
        self._model_discovery: _OpenAIModelDiscovery | None = None
        self.openai_key_status = QLabel()
        self.set_openai_key_button = QPushButton("Set / Change API Key…")
        self.remove_openai_key_button = QPushButton("Remove API Key")
        self.test_openai_button = QPushButton("Test Connection")

        self.set_openai_key_button.clicked.connect(self._set_openai_api_key)
        self.remove_openai_key_button.clicked.connect(self._remove_openai_api_key)
        self.test_openai_button.clicked.connect(self._test_openai_connection)
        self.ai_provider.currentIndexChanged.connect(self._update_ai_controls)

        api_key_buttons = QHBoxLayout()
        api_key_buttons.addWidget(self.set_openai_key_button)
        api_key_buttons.addWidget(self.remove_openai_key_button)
        api_key_buttons.addStretch(1)

        api_key_layout = QVBoxLayout()
        api_key_layout.addWidget(self.openai_key_status)
        api_key_layout.addLayout(api_key_buttons)

        ai_form = QFormLayout()
        ai_form.addRow("Provider", self.ai_provider)
        model_row = QHBoxLayout()
        model_row.addWidget(self.openai_model, 1)
        model_row.addWidget(self.refresh_openai_models_button)
        ai_form.addRow("OpenAI model", model_row)
        ai_form.addRow("", self.openai_model_status)
        ai_form.addRow("OpenAI API key", api_key_layout)
        ai_form.addRow("", self.test_openai_button)
        ai_group = QGroupBox("AI Generation")
        ai_group.setLayout(ai_form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self._settings_buttons = buttons
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(general_group)
        layout.addWidget(renderer_group)
        layout.addWidget(ai_group)
        layout.addWidget(buttons)

        self._refresh_openai_key_status()
        self._update_ai_controls()

    def _browse_comfyui_output_directory(self) -> None:
        current = self.comfyui_output_directory.text().strip()
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select ComfyUI Output Folder",
            current or str(Path.home()),
        )
        if selected:
            self.comfyui_output_directory.setText(selected)

    def _refresh_openai_key_status(self) -> None:
        try:
            key_available = bool(self.credentials.get_openai_api_key())
        except CredentialStorageError as exc:
            self.openai_key_status.setText(f"Credential status unavailable: {exc}")
            self.openai_key_status.setToolTip(str(exc))
            return

        if key_available:
            self.openai_key_status.setText("✓ API key is available from secure storage.")
        else:
            self.openai_key_status.setText("No OpenAI API key is currently configured.")
        self.openai_key_status.setToolTip("")

    def _update_ai_controls(self) -> None:
        openai_enabled = self.ai_provider.currentData() == AIProvider.OPENAI
        self.openai_model.setEnabled(openai_enabled)
        self.refresh_openai_models_button.setEnabled(
            openai_enabled and self._model_discovery is None
        )
        self.openai_key_status.setEnabled(openai_enabled)
        self.set_openai_key_button.setEnabled(openai_enabled)
        self.remove_openai_key_button.setEnabled(openai_enabled)
        self.test_openai_button.setEnabled(openai_enabled)

    def _refresh_openai_models(self) -> None:
        if self._model_discovery is not None:
            return
        try:
            api_key = self.credentials.get_openai_api_key()
            if not api_key:
                raise ValueError("Set an OpenAI API key before refreshing models.")
        except (CredentialStorageError, ValueError) as exc:
            QMessageBox.warning(self, "OpenAI Models", str(exc))
            return
        self.openai_model_status.setText("Retrieving API-visible models…")
        self.refresh_openai_models_button.setEnabled(False)
        self._settings_buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
        worker = _OpenAIModelDiscovery(api_key, self)
        self._model_discovery = worker
        worker.models_loaded.connect(self._models_loaded)
        worker.models_failed.connect(self._models_failed)
        worker.finished.connect(self._model_discovery_finished)
        worker.start()

    def _models_loaded(self, models: tuple[str, ...]) -> None:
        current = self.openai_model.currentText()
        self.openai_model.clear()
        self.openai_model.addItems(models)
        self.openai_model.setCurrentText(current)
        self.openai_model_status.setText(
            f"{len(models)} API-visible models loaded. "
            "Model visibility does not guarantee structured CAP compatibility."
        )

    def _models_failed(self, reason: str) -> None:
        self.openai_model_status.setText(
            "Model retrieval failed; your current selection and manual entry are unchanged."
        )
        QMessageBox.warning(self, "OpenAI Models", reason)

    def _model_discovery_finished(self) -> None:
        worker = self._model_discovery
        self._model_discovery = None
        self._update_ai_controls()
        self._settings_buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(True)
        if worker is not None:
            worker.deleteLater()

    def reject(self) -> None:
        if self._model_discovery is not None:
            QMessageBox.information(
                self,
                "OpenAI Models",
                "Model retrieval is still running. Close Settings after it finishes.",
            )
            return
        super().reject()

    def _set_openai_api_key(self) -> None:
        api_key, accepted = QInputDialog.getText(
            self,
            "Set OpenAI API Key",
            "OpenAI API key:",
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return
        if not api_key.strip():
            QMessageBox.warning(
                self,
                "OpenAI API Key",
                "Enter a non-empty OpenAI API key.",
            )
            return
        try:
            self.credentials.set_openai_api_key(api_key)
        except CredentialStorageError as exc:
            QMessageBox.critical(self, "Credential Storage Error", str(exc))
            return
        self._refresh_openai_key_status()
        QMessageBox.information(
            self,
            "OpenAI API Key",
            "The OpenAI API key was saved securely.",
        )

    def _remove_openai_api_key(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Remove OpenAI API Key",
                "Remove the securely stored OpenAI API key?",
            )
            is not QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.credentials.set_openai_api_key("")
        except CredentialStorageError as exc:
            QMessageBox.critical(self, "Credential Storage Error", str(exc))
            return
        self._refresh_openai_key_status()
        QMessageBox.information(
            self,
            "OpenAI API Key",
            "The securely stored OpenAI API key was removed.",
        )

    def _test_openai_connection(self) -> None:
        model = self.openai_model.currentText().strip()
        try:
            api_key = self.credentials.get_openai_api_key()
            if not api_key:
                raise ValueError("Set an OpenAI API key before testing the connection.")
            OpenAICAPGenerationProvider.test_connection(api_key=api_key, model=model)
        except (AIProviderError, CredentialStorageError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "OpenAI Connection Test", str(exc))
            return
        QMessageBox.information(
            self,
            "OpenAI Connection Test",
            f"Connection succeeded. Model '{model}' is available.",
        )

    def _save(self) -> None:
        if self._model_discovery is not None:
            return
        settings = self.configuration.settings
        settings.theme = self.theme_combo.currentData()
        settings.maximum_recent_projects = self.maximum_recent_spin.value()

        try:
            workspace_payload = settings.workspace.model_dump()
            workspace_payload["restore_last_project"] = self.restore_last_project.isChecked()
            workspace_payload["confirm_before_exit"] = self.confirm_before_exit.isChecked()
            workspace_payload["media_output_directory"] = self.media_output_directory.text().strip()
            settings.workspace = type(settings.workspace).model_validate(workspace_payload)
        except ValueError as exc:
            QMessageBox.critical(self, "Settings Error", str(exc))
            return

        comfyui = settings.renderers.get("comfyui")
        if comfyui is not None:
            renderer_payload = comfyui.model_dump()
            source_text = self.comfyui_output_directory.text().strip()
            renderer_payload["output_directory"] = Path(source_text) if source_text else None
            settings.renderers["comfyui"] = type(comfyui).model_validate(renderer_payload)

        settings.recent_projects = settings.recent_projects[: settings.maximum_recent_projects]
        settings.ai.provider = self.ai_provider.currentData()
        settings.ai.openai_model = self.openai_model.text().strip()
        try:
            self.configuration.save()
        except (CredentialStorageError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Settings Error", str(exc))
            return
        QMessageBox.information(
            self,
            "Settings Saved",
            "Settings were saved. AI provider changes take effect the next time VSCS starts.",
        )
        self.accept()
