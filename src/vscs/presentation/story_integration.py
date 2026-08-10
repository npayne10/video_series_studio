"""Install the Story Workspace into the existing VSCS main window shell."""

from __future__ import annotations

from typing import Any

from vscs.application.acpp import ACPPEditorService
from vscs.application.asset_resolution import (
    AssetBrowserService,
    register_asset_resolution,
)
from vscs.application.assets import AssetService
from vscs.application.shots import ShotPlanningService
from vscs.application.story import (
    EpisodePlanningService,
    ScenePlanningService,
    StoryApprovalService,
    StoryLifecycleService,
    StoryMetadataService,
    StoryService,
    StoryStatusService,
    register_episode_planning,
    register_scene_planning,
    register_story_approval,
    register_story_lifecycle,
    register_story_metadata,
    register_story_status,
)
from vscs.application.story_analysis import (
    ApprovedStoryIntelligenceService,
    StoryAnalysisCacheService,
    StoryAnalysisEngine,
)
from vscs.application.story_analysis.ai_composition import register_ai_story_analysis
from vscs.presentation.dialogs.guided_first_scene_editor_dialog import (
    GuidedFirstSceneEditorDialog,
)
from vscs.presentation.widgets import episode_planner as episode_planner_module
from vscs.presentation.widgets import production_planning_workspace as planning_workspace_module
from vscs.presentation.widgets import story_browser as story_browser_module
from vscs.presentation.widgets.browseable_story_workspace import (
    BrowseableStoryWorkspaceWidget,
)
from vscs.presentation.widgets.episode_planner import install_episode_planner
from vscs.presentation.widgets.iterative_scene_planner import IterativeScenePlannerDialog
from vscs.presentation.widgets.production_planning_workspace import (
    install_production_planning_workspace,
)
from vscs.presentation.windows.main_window import MainWindow


def install_story_browser() -> None:
    """Install the project-aware Story workspace exactly once."""
    if getattr(MainWindow, "_story_browser_installed", False):
        return

    setattr(  # noqa: B010
        story_browser_module,
        "SceneEditorDialog",
        GuidedFirstSceneEditorDialog,
    )
    setattr(  # noqa: B010
        episode_planner_module,
        "ScenePlannerDialog",
        IterativeScenePlannerDialog,
    )
    setattr(  # noqa: B010
        planning_workspace_module,
        "ScenePlannerDialog",
        IterativeScenePlannerDialog,
    )

    original_create_content = MainWindow._create_content_area
    original_update_status = MainWindow._update_status_for_section
    original_update_state = MainWindow._update_project_state
    original_close_project = MainWindow._close_project

    def create_content_area(window: Any) -> None:
        original_create_content(window)
        placeholder = window.content_stack.widget(2)
        asset_browser = window.services.get(AssetBrowserService)
        if asset_browser is None:
            register_asset_resolution(window.services)
            asset_browser = window.services.require(AssetBrowserService)
        if window.services.get(StoryLifecycleService) is None:
            register_story_lifecycle(window.services)
        if window.services.get(StoryMetadataService) is None:
            register_story_metadata(window.services)
        if window.services.get(StoryStatusService) is None:
            register_story_status(window.services)
        if window.services.get(StoryApprovalService) is None:
            register_story_approval(window.services)
        if window.services.get(EpisodePlanningService) is None:
            register_episode_planning(window.services)
        if window.services.get(ScenePlanningService) is None:
            register_scene_planning(window.services)
        register_ai_story_analysis(window.services)
        intelligence = window.services.get(ApprovedStoryIntelligenceService)
        if intelligence is None:
            intelligence = window.services.register(
                ApprovedStoryIntelligenceService,
                ApprovedStoryIntelligenceService(window.services.require(AssetService)),
            )
        analysis_engine = window.services.require(StoryAnalysisEngine)
        analysis_cache = window.services.get(StoryAnalysisCacheService)
        if analysis_cache is None:
            analysis_cache = window.services.register(
                StoryAnalysisCacheService,
                StoryAnalysisCacheService(
                    window.services.require(AssetService),
                    analysis_engine,
                ),
            )
        window.story_browser = BrowseableStoryWorkspaceWidget(
            window.services.require(StoryService),
            window.services.require(AssetService),
            window.services.require(ShotPlanningService),
            window.services.require(ACPPEditorService),
            asset_browser,
            window.services.require(StoryLifecycleService),
            window.services.require(StoryMetadataService),
            window.services.require(StoryStatusService),
            window.services.require(StoryApprovalService),
        )
        window.story_browser.analysis_engine = analysis_engine
        window.story_browser.analysis_cache = analysis_cache
        window.story_browser.intelligence_service = intelligence
        episode_service = window.services.require(EpisodePlanningService)
        scene_service = window.services.require(ScenePlanningService)
        window.episode_planner_button = install_episode_planner(
            window.story_browser,
            episode_service,
            scene_service,
        )
        window.episode_planner_button.setText("Production Planning…")
        window.episode_planner_button.setToolTip(
            "Open the authoritative Episode → Scene → Shot production-planning environment"
        )
        window.open_in_planner_button = install_production_planning_workspace(
            window.story_browser,
            episode_service,
            scene_service,
        )
        window.story_workspace = window.story_browser
        window.content_stack.removeWidget(placeholder)
        placeholder.deleteLater()
        window.content_stack.insertWidget(2, window.story_browser)

    def update_status(window: Any, section: str) -> None:
        original_update_status(window, section)
        if section == "Story":
            window.story_browser.refresh()

    def update_state(window: Any) -> None:
        original_update_state(window)
        window.story_browser.refresh()

    def close_project(window: Any) -> None:
        original_close_project(window)
        window.story_browser.refresh()

    setattr(MainWindow, "_create_content_area", create_content_area)  # noqa: B010
    setattr(MainWindow, "_update_status_for_section", update_status)  # noqa: B010
    setattr(MainWindow, "_update_project_state", update_state)  # noqa: B010
    setattr(MainWindow, "_close_project", close_project)  # noqa: B010
    setattr(MainWindow, "_story_browser_installed", True)  # noqa: B010
