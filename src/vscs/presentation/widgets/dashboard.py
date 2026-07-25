"""Dashboard shown when VSCS starts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class DashboardWidget(QWidget):
    """Welcome dashboard for the VSCS application shell."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(18)

        title = QLabel("Video Series Studio")
        title.setObjectName("dashboardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        subtitle = QLabel(
            "Create, plan, manage, and produce cinematic video series from structured story data."
        )
        subtitle.setObjectName("dashboardSubtitle")
        subtitle.setWordWrap(True)

        actions = QHBoxLayout()
        actions.setSpacing(12)

        self.new_project_button = QPushButton("New Project")
        self.new_project_button.setObjectName("newProjectButton")
        self.open_project_button = QPushButton("Open Project")
        self.open_project_button.setObjectName("openProjectButton")

        actions.addWidget(self.new_project_button)
        actions.addWidget(self.open_project_button)
        actions.addStretch()

        self.project_panel = QFrame()
        self.project_panel.setObjectName("activeProjectPanel")
        project_layout = QVBoxLayout(self.project_panel)
        project_layout.setContentsMargins(24, 20, 24, 20)

        project_title = QLabel("Active Project")
        project_title.setObjectName("sectionTitle")
        self.project_name_label = QLabel("No project open")
        self.project_name_label.setObjectName("activeProjectName")
        self.project_path_label = QLabel("")
        self.project_path_label.setObjectName("activeProjectPath")
        self.project_path_label.setWordWrap(True)

        project_layout.addWidget(project_title)
        project_layout.addWidget(self.project_name_label)
        project_layout.addWidget(self.project_path_label)

        overview = QFrame()
        overview.setObjectName("overviewPanel")
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(24, 20, 24, 20)

        overview_title = QLabel("Framework Status")
        overview_title.setObjectName("sectionTitle")
        overview_text = QLabel(
            "Application shell ready. Project management, story planning, assets, production, "
            "rendering, and post-production modules will be added in later tasks."
        )
        overview_text.setWordWrap(True)

        overview_layout.addWidget(overview_title)
        overview_layout.addWidget(overview_text)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(actions)
        layout.addSpacing(12)
        layout.addWidget(self.project_panel)
        layout.addWidget(overview)
        layout.addStretch()

        self.clear_active_project()

    def set_active_project(self, project_name: str, project_directory: Path | str) -> None:
        """Display the currently opened project on the dashboard."""
        self.project_name_label.setText(project_name)
        self.project_path_label.setText(str(project_directory))
        self.project_panel.setVisible(True)

    def clear_active_project(self) -> None:
        """Reset the dashboard when no project is open."""
        self.project_name_label.setText("No project open")
        self.project_path_label.clear()
        self.project_panel.setVisible(True)
