"""Main application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from vscs.infrastructure.configuration import ConfigurationService
from vscs.presentation.dialogs.settings_dialog import SettingsDialog
from vscs.presentation.widgets.dashboard import DashboardWidget


class MainWindow(QMainWindow):
    """Primary window for the Video Series Studio desktop application."""

    def __init__(self, configuration: ConfigurationService) -> None:
        super().__init__()
        self.configuration = configuration
        self.setObjectName("mainWindow")
        self.setWindowTitle("Video Series Studio — VSCS Framework v0.1")
        self.resize(1440, 900)
        self.setMinimumSize(1024, 680)

        self._create_actions()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_navigation()
        self._create_content_area()
        self._connect_signals()
        self._restore_default_workspace()

        self.statusBar().showMessage(f"Ready — {self.configuration.config_path}")

    def _create_actions(self) -> None:
        self.new_project_action = QAction("New Project", self)
        self.new_project_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_project_action.setStatusTip("Create a new VSCS project")

        self.open_project_action = QAction("Open Project", self)
        self.open_project_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_project_action.setStatusTip("Open an existing VSCS project")

        self.save_project_action = QAction("Save Project", self)
        self.save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_project_action.setStatusTip("Save the current project")
        self.save_project_action.setEnabled(False)

        self.settings_action = QAction("Settings", self)
        self.settings_action.setStatusTip("Edit application preferences")
        self.settings_action.triggered.connect(self._show_settings_dialog)

        self.exit_action = QAction("Exit", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self.close)

        self.about_action = QAction("About VSCS", self)
        self.about_action.triggered.connect(self._show_about_dialog)

    def _create_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.save_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction("Dashboard", lambda: self._select_navigation_item(0))

        tools_menu = self.menuBar().addMenu("&Tools")
        tools_menu.addAction(self.settings_action)
        tools_menu.addAction("Plugin Manager", self._show_not_implemented)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.new_project_action)
        toolbar.addAction(self.open_project_action)
        toolbar.addAction(self.save_project_action)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _create_navigation(self) -> None:
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigationList")
        self.navigation.setMinimumWidth(210)

        sections = (
            "Dashboard",
            "Projects",
            "Story",
            "Assets",
            "Production Planning",
            "Render Queue",
            "Post-Production",
        )
        for section in sections:
            self.navigation.addItem(QListWidgetItem(section))

        navigation_dock = QDockWidget("Workspace", self)
        navigation_dock.setObjectName("navigationDock")
        navigation_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        navigation_dock.setWidget(self.navigation)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, navigation_dock)

    def _create_content_area(self) -> None:
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")

        self.dashboard = DashboardWidget()
        self.content_stack.addWidget(self.dashboard)

        for section in (
            "Projects",
            "Story",
            "Assets",
            "Production Planning",
            "Render Queue",
            "Post-Production",
        ):
            self.content_stack.addWidget(self._placeholder_page(section))

        self.setCentralWidget(self.content_stack)
        self.navigation.setCurrentRow(0)

    def _connect_signals(self) -> None:
        self.navigation.currentRowChanged.connect(self.content_stack.setCurrentIndex)
        self.navigation.currentTextChanged.connect(self._update_status_for_section)

        self.new_project_action.triggered.connect(self._show_not_implemented)
        self.open_project_action.triggered.connect(self._show_not_implemented)
        self.dashboard.new_project_button.clicked.connect(self.new_project_action.trigger)
        self.dashboard.open_project_button.clicked.connect(self.open_project_action.trigger)

    def _restore_default_workspace(self) -> None:
        default_workspace = self.configuration.settings.workspace.default_workspace
        matches = self.navigation.findItems(default_workspace, Qt.MatchFlag.MatchExactly)
        if matches:
            self.navigation.setCurrentItem(matches[0])

    def _placeholder_page(self, title: str) -> QWidget:
        label = QLabel(f"{title}\nModule planned for a later development task")
        label.setObjectName(f"{title.lower().replace(' ', '')}Placeholder")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        return label

    def _select_navigation_item(self, row: int) -> None:
        self.navigation.setCurrentRow(row)

    def _update_status_for_section(self, section: str) -> None:
        if section:
            self.statusBar().showMessage(f"Workspace: {section}")

    def _show_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.configuration, self)
        if dialog.exec():
            self.statusBar().showMessage("Settings saved", 3000)

    def _show_not_implemented(self) -> None:
        QMessageBox.information(
            self,
            "VSCS Framework",
            "This function is reserved for a later development task.",
        )

    def _show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            "About Video Series Studio",
            "Video Series Studio (VSCS)\nFramework version 0.1\n\n"
            "A production platform for planning and creating cinematic video series.",
        )
