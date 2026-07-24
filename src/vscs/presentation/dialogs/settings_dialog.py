"""Application settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vscs.infrastructure.ai import AICredentialStore, CredentialStorageError
from vscs.infrastructure.configuration import AIProvider, ConfigurationService, Theme


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
        self.setMinimumWidth(480)

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

        general_form = QFormLayout()
        general_form.addRow("Theme", self.theme_combo)
        general_form.addRow("Maximum recent projects", self.maximum_recent_spin)
        general_form.addRow("Restore last project", self.restore_last_project)
        general_form.addRow("Confirm before exit", self.confirm_before_exit)
        general_group = QGroupBox("General")
        general_group.setLayout(general_form)

        self.ai_provider = QComboBox()
        for provider in AIProvider:
            self.ai_provider.addItem(provider.value.title(), provider)
        self.ai_provider.setCurrentIndex(
            self.ai_provider.findData(configuration.settings.ai.provider)
        )
        self.openai_model = QLineEdit(configuration.settings.ai.openai_model)
        self.openai_api_key = QLineEdit()
        self.openai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_api_key.setPlaceholderText(
            "Leave unchanged to keep the current securely stored key"
        )
        self.ai_provider.currentIndexChanged.connect(self._update_ai_controls)

        ai_form = QFormLayout()
        ai_form.addRow("Provider", self.ai_provider)
        ai_form.addRow("OpenAI model", self.openai_model)
        ai_form.addRow("OpenAI API key", self.openai_api_key)
        ai_group = QGroupBox("AI Generation")
        ai_group.setLayout(ai_form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(general_group)
        layout.addWidget(ai_group)
        layout.addWidget(buttons)
        self._update_ai_controls()

    def _update_ai_controls(self) -> None:
        openai_enabled = self.ai_provider.currentData() is AIProvider.OPENAI
        self.openai_model.setEnabled(openai_enabled)
        self.openai_api_key.setEnabled(openai_enabled)

    def _save(self) -> None:
        settings = self.configuration.settings
        settings.theme = self.theme_combo.currentData()
        settings.maximum_recent_projects = self.maximum_recent_spin.value()
        settings.workspace.restore_last_project = self.restore_last_project.isChecked()
        settings.workspace.confirm_before_exit = self.confirm_before_exit.isChecked()
        settings.recent_projects = settings.recent_projects[: settings.maximum_recent_projects]
        settings.ai.provider = self.ai_provider.currentData()
        settings.ai.openai_model = self.openai_model.text()
        try:
            if self.openai_api_key.text():
                self.credentials.set_openai_api_key(self.openai_api_key.text())
            self.configuration.save()
        except (CredentialStorageError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Settings Error", str(exc))
            return
        QMessageBox.information(
            self,
            "Settings Saved",
            "AI provider changes will take effect the next time VSCS starts.",
        )
        self.accept()
