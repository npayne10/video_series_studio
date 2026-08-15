from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from vscs.application.automation import (
    AutomationProposalService,
    AutomationProposalType,
    SceneShotProposalAutomationService,
)
from vscs.application.projects import ProjectService
from vscs.application.story import (
    GovernedShotPlanningService,
    StoryLifecycleService,
    StorySourceType,
)
from vscs.application.story_analysis import StoryAnalysisCacheService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.toml",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def test_scene_shot_automation_is_registered_with_story_workspace(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        service = application.services.get(SceneShotProposalAutomationService)
        workspace = window.story_browser

        assert isinstance(service, SceneShotProposalAutomationService)
        # Phase 19.5.12A relocates these actions into hierarchical navigation.
        assert workspace.shot_proposals_button.isHidden()
        assert workspace.shot_proposals_button.text() == "Shot Proposals…"
        assert workspace.review_proposals_button.isHidden()
        assert workspace.review_proposals_button.text() == "Review Proposals…"


def test_story_workspace_generates_shot_proposals_without_creating_shot_authority(
    tmp_path: Path,
    qtbot,
    monkeypatch,
) -> None:
    source = tmp_path / "The Silent Relay.txt"
    source_text = (
        "Commander James Spence stood on the Iron Horizon bridge.\n\n"
        "The Signal\n\nSandra detected a repeating emergency transmission. "
        "James ordered the signal played and the crew decided to investigate."
    )
    source.write_text(source_text, encoding="utf-8")

    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        lifecycle = application.services.require(StoryLifecycleService)
        story = lifecycle.create_story(
            title="The Silent Relay",
            source_type=StorySourceType.PLAIN_TEXT,
            source_path=str(source),
        )
        cache = application.services.require(StoryAnalysisCacheService)
        report = cache.analyze(story, source_text)
        assert report.status.value == "completed"

        workspace = window.story_browser
        workspace.refresh()
        workspace.story_list.setCurrentRow(0)
        monkeypatch.setattr(QMessageBox, "information", lambda *_args, **_kwargs: None)

        workspace.planning_proposals_button.click()
        workspace.shot_proposals_button.click()

        proposals = application.services.require(AutomationProposalService).list_proposals()
        shot_proposals = tuple(
            item for item in proposals if item.proposal_type is AutomationProposalType.SHOT
        )
        assert shot_proposals
        assert all(item.status.value == "proposed" for item in shot_proposals)
        assert all(item.metadata.get("parent_scene_proposal_id") for item in shot_proposals)
        assert application.services.require(GovernedShotPlanningService).list_plans() == ()
