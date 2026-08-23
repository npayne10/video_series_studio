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
from vscs.application.behaviours import ensure_behaviour_profile_service
from vscs.application.caps import (
    CanonicalReferenceService,
    CAPBehaviourIntegrationService,
    CAPGeneratorService,
    CAPService,
    ProductionProjectionService,
)
from vscs.application.generated_media import GeneratedMediaUiService
from vscs.application.production_execution import ProductionExecutionUiService
from vscs.application.projects import ProjectError, ProjectService
from vscs.application.provider_capability_validation import ProviderCapabilityValidationService
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.generated_media import (
    JsonGeneratedMediaRepository,
    JsonGeneratedMediaSelectionRepository,
)
from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.plugins import PluginManager
from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend
from vscs.infrastructure.provider_capability_validation import (
    JsonCapabilityValidationRepository,
    wan22_video_validation_pack,
)
from vscs.infrastructure.services import ApplicationServices
from vscs.presentation.dialogs.plugin_manager_dialog import PluginManagerDialog
from vscs.presentation.dialogs.settings_dialog import SettingsDialog
from vscs.presentation.widgets.asset_manager import AssetManagerWidget
from vscs.presentation.widgets.asset_readiness_column import install_asset_readiness_column
from vscs.presentation.widgets.behaviour_profile_manager import BehaviourProfileManagerWidget
from vscs.presentation.widgets.cap_behaviour_profiles import install_cap_behaviour_profiles
from vscs.presentation.widgets.cap_derived_reference_generation import (
    install_derived_reference_generation,
)
from vscs.presentation.widgets.cap_manager import CAPManagerWidget
from vscs.presentation.widgets.cap_readiness_widget import install_cap_readiness
from vscs.presentation.widgets.dashboard import DashboardWidget
from vscs.presentation.widgets.generated_media_workspace import GeneratedMediaWorkspaceWidget
from vscs.presentation.widgets.production_execution_workspace import ProductionExecutionWorkspace
from vscs.presentation.widgets.provider_capability_validation_workspace import (
    ProviderCapabilityValidationWorkspace,
)


class MainWindow(QMainWindow):
    """Primary window for the Video Series Studio desktop application."""

    BASE_TITLE = "Video Series Studio — VSCS Framework v0.1"

    def __init__(self, services: ApplicationServices) -> None:
        super().__init__()
        self.services = services
        self.configuration = services.require(ConfigurationService)
        self.projects = services.require(ProjectService)
        self.assets = services.require(AssetService)
        self.caps = services.require(CAPService)
        self.behaviours = ensure_behaviour_profile_service(services)
        self._production_execution_project: Path | None = None
        self._production_execution_ui: ProductionExecutionUiService | None = None
        cap_behaviour_integration = services.get(CAPBehaviourIntegrationService)
        if cap_behaviour_integration is None:
            cap_behaviour_integration = services.register(
                CAPBehaviourIntegrationService,
                CAPBehaviourIntegrationService(self.caps, self.behaviours),
            )
        self.cap_behaviour_integration = cap_behaviour_integration
        self.cap_generator = services.get(CAPGeneratorService)
        self.canonical_references = services.get(CanonicalReferenceService)
        self.production_projection = services.get(ProductionProjectionService)
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
        for action in (
            self.new_project_action,
            self.open_project_action,
            self.save_project_action,
            self.close_project_action,
        ):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction("Dashboard", lambda: self._select_navigation_item(0))
        view_menu.addAction("Assets", lambda: self._select_navigation_item(3))
        view_menu.addAction("Canonical Profiles", lambda: self._select_navigation_item(4))
        view_menu.addAction("Behaviour Profiles", lambda: self._select_navigation_item(5))
        view_menu.addAction("Production Execution", lambda: self._select_navigation_item(7))
        view_menu.addAction("Generated Media", lambda: self._select_navigation_item(8))
        view_menu.addAction("Provider Validation", lambda: self._select_navigation_item(9))
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
            "Canonical Profiles",
            "Behaviour Profiles",
            "Production Planning",
            "Production Execution",
            "Generated Media",
            "Provider Validation",
            "Post-Production",
        )
        for section in sections:
            self.navigation.addItem(QListWidgetItem(section))
        self.navigation_dock = QDockWidget("Workspace", self)
        self.navigation_dock.setObjectName("navigationDock")
        self.navigation_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.navigation_dock.setWidget(self.navigation)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.navigation_dock)

    def _create_content_area(self) -> None:
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")
        self.dashboard = DashboardWidget()
        self.content_stack.addWidget(self.dashboard)
        self.content_stack.addWidget(self._placeholder_page("Projects"))
        self.content_stack.addWidget(self._placeholder_page("Story"))
        self.asset_manager = AssetManagerWidget(
            self.assets,
            self.caps,
            self.canonical_references,
        )
        self.asset_readiness_service = install_asset_readiness_column(
            self.asset_manager,
            self.caps,
            self.canonical_references,
        )
        self.content_stack.addWidget(self.asset_manager)
        self.cap_manager = CAPManagerWidget(
            self.caps,
            self.cap_generator,
            self.canonical_references,
        )
        self.derived_reference_button = install_derived_reference_generation(self.cap_manager)
        self.cap_readiness_button = install_cap_readiness(
            self.cap_manager,
            self.production_projection,
        )
        self.cap_behaviour_profiles_button = install_cap_behaviour_profiles(
            self.cap_manager,
            self.cap_behaviour_integration,
        )
        self.content_stack.addWidget(self.cap_manager)
        self.behaviour_manager = BehaviourProfileManagerWidget(
            self.behaviours,
            project_available=lambda: self.projects.is_project_open,
        )
        self.content_stack.addWidget(self.behaviour_manager)
        self.content_stack.addWidget(self._placeholder_page("Production Planning"))
        self.production_execution_workspace = ProductionExecutionWorkspace(
            self._production_execution_ui_service
        )
        self.content_stack.addWidget(self.production_execution_workspace)
        self.generated_media_workspace = GeneratedMediaWorkspaceWidget(
            self._generated_media_ui_service
        )
        self.content_stack.addWidget(self.generated_media_workspace)
        self.provider_validation_workspace = ProviderCapabilityValidationWorkspace(
            self._provider_capability_validation_service
        )
        self.content_stack.addWidget(self.provider_validation_workspace)
        self.content_stack.addWidget(self._placeholder_page("Post-Production"))
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
        self.asset_manager.open_canonical_profile_requested.connect(self._open_canonical_profile)

    def _restore_default_workspace(self) -> None:
        default_workspace = self.configuration.settings.workspace.default_workspace
        matches = self.navigation.findItems(default_workspace, Qt.MatchFlag.MatchExactly)
        if matches:
            self.navigation.setCurrentItem(matches[0])

    def _placeholder_page(self, title: str) -> QWidget:
        label = QLabel(f"{title}\nModule planned for a later development task")
        label.setObjectName(f"{title.lower().replace(' ', '')}Placeholder")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _update_status_for_section(self, section: str) -> None:
        self.statusBar().showMessage(f"Workspace: {section}")
        if section == "Assets":
            self.asset_manager.refresh()
        elif section == "Canonical Profiles":
            self.cap_manager.refresh()
        elif section == "Behaviour Profiles":
            self.behaviour_manager.refresh()
        elif section == "Production Execution":
            self.production_execution_workspace.refresh()
        elif section == "Generated Media":
            self.generated_media_workspace.refresh()
        elif section == "Provider Validation":
            self.provider_validation_workspace.refresh()

    def _select_navigation_item(self, row: int) -> None:
        self.navigation.setCurrentRow(row)

    def _open_canonical_profile(self, asset_id: str) -> None:
        """Navigate from Asset editing to the canonical governance workspace."""
        self._select_navigation_item(4)
        self.cap_manager.refresh()
        self.statusBar().showMessage(f"Canonical Profiles — {asset_id}", 5000)

    def _generated_media_ui_service(self) -> GeneratedMediaUiService | None:
        project_directory = self.projects.project_directory
        if project_directory is None:
            return None
        root = project_directory / ".vscs"
        return GeneratedMediaUiService(
            media_repository_factory=lambda: JsonGeneratedMediaRepository(root / "generated_media"),
            selection_repository_factory=lambda: JsonGeneratedMediaSelectionRepository(
                root / "generated_media_selections"
            ),
        )

    def _provider_capability_validation_service(
        self,
    ) -> ProviderCapabilityValidationService | None:
        project_directory = self.projects.project_directory
        if project_directory is None:
            return None
        root = project_directory / ".vscs"
        return ProviderCapabilityValidationService(
            JsonCapabilityValidationRepository(root / "provider_capability_validation"),
            JsonGeneratedMediaRepository(root / "generated_media"),
            (wan22_video_validation_pack(),),
        )

    def _production_execution_ui_service(self) -> ProductionExecutionUiService | None:
        project_directory = self.projects.project_directory
        if project_directory is None:
            self._production_execution_project = None
            self._production_execution_ui = None
            return None
        resolved = project_directory.resolve(strict=False)
        if (
            self._production_execution_project == resolved
            and self._production_execution_ui is not None
        ):
            return self._production_execution_ui
        renderer = self.configuration.settings.renderers.get("comfyui")
        endpoint = (
            renderer.api_url
            if renderer is not None and renderer.api_url
            else self.configuration.settings.environment.comfyui_url
        )
        source_output = renderer.output_directory if renderer is not None else None
        backend = LocalComfyUIProductionExecutionBackend(
            resolved,
            endpoint=endpoint,
            comfyui_output_directory=source_output,
            managed_media_directory=self.configuration.settings.workspace.media_output_directory,
        )
        self._production_execution_project = resolved
        self._production_execution_ui = ProductionExecutionUiService(backend)
        return self._production_execution_ui

    def _create_project(self) -> None:
        name, accepted = QInputDialog.getText(self, "New Project", "Project name:")
        project_name = name.strip()
        if not accepted or not project_name:
            return
        parent_directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Project Parent Directory",
            str(Path.home()),
        )
        if not parent_directory:
            return
        project_directory = Path(parent_directory) / project_name
        try:
            project = self.projects.create(project_directory, name=project_name)
        except ProjectError as exc:
            QMessageBox.critical(self, "Project Error", str(exc))
            return
        self._reset_production_execution()
        self._update_project_state()
        self.dashboard.set_active_project(project.name, project_directory)
        self.statusBar().showMessage(f"Created project: {project.name}", 5000)

    def _open_project(self) -> None:
        project_directory = QFileDialog.getExistingDirectory(
            self,
            "Open VSCS Project",
            str(Path.home()),
        )
        if not project_directory:
            return
        project_path = Path(project_directory)
        try:
            project = self.projects.open(project_path)
        except ProjectError as exc:
            QMessageBox.critical(self, "Project Error", str(exc))
            return
        self._reset_production_execution()
        self._update_project_state()
        self.dashboard.set_active_project(project.name, project_path)
        self.statusBar().showMessage(f"Opened project: {project.name}", 5000)

    def _save_project(self) -> None:
        try:
            self.projects.save()
        except ProjectError as exc:
            QMessageBox.critical(self, "Project Error", str(exc))
            return
        project = self.projects.current_project
        if project is not None:
            self.statusBar().showMessage(f"Saved project: {project.name}", 5000)

    def _close_project(self) -> None:
        if not self.projects.is_project_open:
            return
        if (
            QMessageBox.question(self, "Close Project", "Close the active project?")
            is not QMessageBox.StandardButton.Yes
        ):
            return
        self.projects.close()
        self._reset_production_execution()
        self._update_project_state()
        self.dashboard.clear_active_project()
        self.asset_manager.refresh()
        self.cap_manager.refresh()
        self.behaviour_manager.refresh()
        self.production_execution_workspace.refresh()
        self.generated_media_workspace.refresh()
        self.provider_validation_workspace.refresh()
        self.statusBar().showMessage("Project closed", 5000)

    def _reset_production_execution(self) -> None:
        self._production_execution_project = None
        self._production_execution_ui = None

    def _show_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.configuration, self)
        if dialog.exec():
            self._reset_production_execution()
            self.production_execution_workspace.refresh()

    def _show_plugin_manager(self) -> None:
        PluginManagerDialog(self.plugins, self).exec()

    def _show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            "About VSCS",
            "Video Series Studio\nVSCS Framework v0.1\n\n"
            "A professional production platform for cinematic television series.",
        )

    def _update_project_state(self) -> None:
        """Synchronize all project-aware interface elements."""
        active = self.projects.is_project_open
        self.new_project_action.setEnabled(not active)
        self.open_project_action.setEnabled(not active)
        self.save_project_action.setEnabled(active)
        self.close_project_action.setEnabled(active)
        self.asset_manager.add_button.setEnabled(active)
        self.asset_manager.edit_button.setEnabled(active)
        self.cap_manager.add_button.setEnabled(active)
        self.behaviour_manager.new_button.setEnabled(active)
        if self.derived_reference_button is not None:
            self.derived_reference_button.setEnabled(active)
        if self.cap_readiness_button is not None:
            self.cap_readiness_button.setEnabled(active)
        if not active:
            self.cap_behaviour_profiles_button.setEnabled(False)
        self.dashboard.new_project_button.setEnabled(not active)
        self.dashboard.open_project_button.setEnabled(not active)

        self.asset_manager.refresh()
        self.cap_manager.refresh()
        self.behaviour_manager.refresh()
        self.production_execution_workspace.refresh()
        self.generated_media_workspace.refresh()
        self.provider_validation_workspace.refresh()

        if active and self.projects.current_project is not None:
            project = self.projects.current_project
            project_directory = self.projects.project_directory
            assert project_directory is not None
            self.setWindowTitle(f"{self.BASE_TITLE} — {project.name}")
            self.navigation_dock.setWindowTitle(project.name)
            self.dashboard.set_active_project(project.name, project_directory)
            self.statusBar().showMessage(f"Active project: {project.name}")
        else:
            self.setWindowTitle(self.BASE_TITLE)
            self.navigation_dock.setWindowTitle("Workspace")
            self.dashboard.clear_active_project()
            self.statusBar().showMessage("No project open")
