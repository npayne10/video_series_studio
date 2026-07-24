"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from vscs.application.assets import AssetService
from vscs.application.projects import ProjectError, ProjectService
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.plugins import PluginManager
from vscs.infrastructure.services import ApplicationServices
from vscs.presentation.dialogs.plugin_manager_dialog import PluginManagerDialog
from vscs.presentation.dialogs.settings_dialog import SettingsDialog
from vscs.presentation.widgets.asset_manager import AssetManagerWidget
from vscs.presentation.widgets.dashboard import DashboardWidget


class MainWindow(QMainWindow):
    """Primary window for the Video Series Studio desktop application."""

    BASE_TITLE = "Video Series Studio — VSCS Framework v0.1"

    def __init__(self, services: ApplicationServices) -> None:
        super().__init__()
        self.services = services
        self.configuration = services.require(ConfigurationService)
        self.projects = services.require(ProjectService)
        self.assets = services.require(AssetService)
        self.plugins = services.require(PluginManager)
        self.logger = LoggingService.get_logger("presentation.main_window")
        self.setObjectName("mainWindow")
        self.setWindowTitle(self.BASE_TITLE)
        self.resize(1440, 900)
        self.setMinimumSize(1024, 680)

        self._create_actions()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_navigation()
        self._create_content_area()
        self._connect_signals()
        self._restore_default_workspace()
        self._update_project_state()

        self.logger.info("Main window initialized")

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

        self.close_project_action = QAction("Close Project", self)
        self.close_project_action.setStatusTip("Close the current project")

        self.settings_action = QAction("Settings", self)
        self.settings_action.setStatusTip("Edit application preferences")
        self.settings_action.triggered.connect(self._show_settings_dialog)

        self.plugin_manager_action = QAction("Plugin Manager", self)
        self.plugin_manager_action.setStatusTip("Manage VSCS extensions and capabilities")
        self.plugin_manager_action.triggered.connect(self._show_plugin_manager)

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
        file_menu.addAction(self.close_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction("Dashboard", lambda: self._select_navigation_item(0))
        view_menu.addAction("Assets", lambda: self._select_navigation_item(3))

        tools_menu = self.menuBar().addMenu("&Tools")
        tools_menu.addAction(self.settings_action)
        tools_menu.addAction(self.plugin_manager_action)

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
        self.content_stack.addWidget(self._placeholder_page("Projects"))
        self.content_stack.addWidget(self._placeholder_page("Story"))

        self.asset_manager = AssetManagerWidget(self.assets)
        self.content_stack.addWidget(self.asset_manager)

        for section in ("Production Planning", "Render Queue", "Post-Production"):
            self.content_stack.addWidget(self._placeholder_page(section))

        self.setCentralWidget(self.content_stack)
        self.navigation.setCurrentRow(0)

    def _connect_signals(self) -> None:
        self.navigation.currentRowChanged.connect(self.content_stack.setCurrentIndex)
        self.navigation.currentTextChanged.connect(self._update_status_for_section)

        self.new_project_action.triggered.connect(self._create_project)
        self.open_project_action.triggered.connect(self._open_project)
        self.save_project_action.triggered.connect(self._save_project)
        self.close_project_action.triggered.connect(self._close_project)
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

    def _create_project(self) -> None:
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Select New Project Directory",
            str(Path.home()),
        )
        if not selected_directory:
            return
        default_name = Path(selected_directory).name
        name, accepted = QInputDialog.getText(
            self,
            "New VSCS Project",
            "Project name:",
            text=default_name,
        )
        if not accepted or not name.strip():
            return
        try:
            self.projects.create(Path(selected_directory), name=name)
        except ProjectError as exc:
            self._show_project_error(exc)
            return
        self._update_project_state("Project created")

    def _open_project(self) -> None:
        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Open VSCS Project",
            str(Path.home()),
            "VSCS Projects (project.vscs *.vscs);;All Files (*)",
        )
        if not selected_file:
            return
        try:
            self.projects.open(Path(selected_file))
        except ProjectError as exc:
            self._show_project_error(exc)
            return
        self._update_project_state("Project opened")

    def _save_project(self) -> None:
        try:
            self.projects.save()
        except ProjectError as exc:
            self._show_project_error(exc)
            return
        self._update_project_state("Project saved")

    def _close_project(self) -> None:
        try:
            self.projects.close()
        except ProjectError as exc:
            self._show_project_error(exc)
            return
        self._update_project_state("Project closed")

    def _update_project_state(self, message: str | None = None) -> None:
        is_open = self.projects.is_project_open
        self.new_project_action.setEnabled(not is_open)
        self.open_project_action.setEnabled(not is_open)
        self.save_project_action.setEnabled(is_open)
        self.close_project_action.setEnabled(is_open)
        self.asset_manager.refresh()

        if self.projects.current_project is None:
            self.setWindowTitle(self.BASE_TITLE)
            status = message or f"Ready — {self.configuration.config_path}"
        else:
            name = self.projects.current_project.name
            self.setWindowTitle(f"{name} — {self.BASE_TITLE}")
            status = message or f"Project: {name}"
        self.statusBar().showMessage(status, 3000 if message else 0)

    def _show_project_error(self, error: ProjectError) -> None:
        self.logger.error("Project operation failed: %s", error)
        QMessageBox.critical(self, "Project Error", str(error))

    def _show_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.configuration, self)
        if dialog.exec():
            self.logger.info("Application settings updated")
            self.statusBar().showMessage("Settings saved", 3000)

    def _show_plugin_manager(self) -> None:
        PluginManagerDialog(self.plugins, self).exec()

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
