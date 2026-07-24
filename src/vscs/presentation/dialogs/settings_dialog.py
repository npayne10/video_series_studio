"""Application settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vscs.infrastructure.configuration import ConfigurationService, Theme


class SettingsDialog(QDialog):
    """Edit commonly used VSCS preferences."""

    def __init__(
        self,
        configuration: ConfigurationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.configuration = configuration
        self.setWindowTitle("VSCS Settings")
        self.setMinimumWidth(420)

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

        form = QFormLayout()
        form.addRow("Theme", self.theme_combo)
        form.addRow("Maximum recent projects", self.maximum_recent_spin)
        form.addRow("Restore last project", self.restore_last_project)
        form.addRow("Confirm before exit", self.confirm_before_exit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _save(self) -> None:
        settings = self.configuration.settings
        settings.theme = self.theme_combo.currentData()
        settings.maximum_recent_projects = self.maximum_recent_spin.value()
        settings.workspace.restore_last_project = self.restore_last_project.isChecked()
        settings.workspace.confirm_before_exit = self.confirm_before_exit.isChecked()
        settings.recent_projects = settings.recent_projects[: settings.maximum_recent_projects]
        self.configuration.save()
        self.accept()
