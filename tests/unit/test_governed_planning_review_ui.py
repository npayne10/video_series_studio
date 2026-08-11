from __future__ import annotations

from pathlib import Path

from vscs.application.projects import ProjectService
from vscs.application.shots import ShotPlanningService
from vscs.application.story import (
    EpisodePlanningService,
    GovernedPlanningReviewService,
    GovernedShotPlanningService,
    PlanningCheckStatus,
    PlanningReviewCheck,
    PlanningReviewSnapshot,
    ScenePlanningService,
    ShotPlan,
    ShotPlanStatus,
    StoryLifecycleService,
    StoryService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.governed_environment_planner import GovernedEnvironmentPlannerDialog
from vscs.presentation.widgets.governed_planning_review import GovernedPlanningReviewDialog
from vscs.presentation.widgets.governed_shot_planner import GovernedShotPlannerDialog
from vscs.presentation.widgets.planning_review_integration import install_planning_review_navigation


class FakeReviewService:
    def snapshot(self, shot_id: str) -> PlanningReviewSnapshot:
        return PlanningReviewSnapshot(
            shot_id,
            (
                PlanningReviewCheck("Shot", PlanningCheckStatus.PASS, "Ready and current"),
                PlanningReviewCheck("Assets", PlanningCheckStatus.BLOCKED, "Binding is stale"),
                PlanningReviewCheck("Camera", PlanningCheckStatus.PASS, "Ready and current"),
                PlanningReviewCheck("Lighting", PlanningCheckStatus.PASS, "Ready and current"),
                PlanningReviewCheck("Environment", PlanningCheckStatus.PASS, "Ready and current"),
            ),
            "fingerprint",
        )

    def review(self, _shot_id: str):
        return None


def _shot() -> ShotPlan:
    return ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id="EP-001-SCN-001",
        sequence_number=1,
        title="Orbital arrival",
        narrative_purpose="Establish Xorix",
        production_objective="Show physically credible orbital scale",
        target_runtime_seconds=12,
        required_action="Ship crosses frame",
        scene_contract_hash="scene",
        status=ShotPlanStatus.READY,
    )


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def test_planning_review_shows_all_authorities_and_blocks_approval(qtbot) -> None:
    dialog = GovernedPlanningReviewDialog(
        FakeReviewService(),  # type: ignore[arg-type]
        _shot(),
    )
    qtbot.addWidget(dialog)

    assert dialog.checks.rowCount() == 5
    assert dialog.checks.item(1, 0).text() == "Assets"
    assert dialog.checks.item(1, 1).text() == "BLOCKED"
    assert not dialog.approve_button.isEnabled()
    assert "does not edit" in dialog.summary.text()


def test_planning_review_is_owned_by_shot_planner_and_openable_before_specialists_ready(
    qtbot,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    lifecycle = StoryLifecycleService(projects)
    story = lifecycle.create_story(title="Xorix")
    episodes = EpisodePlanningService(projects, lifecycle)
    episode = episodes.create(
        story_id=story.story_id,
        sequence_number=1,
        title="Arrival",
        story_scope="Arrival in orbit.",
        production_objective="Establish Xorix.",
        target_runtime_seconds=600,
    )
    episode = episodes.mark_ready(episode.episode_id)
    scenes = ScenePlanningService(projects, episodes, StoryService(projects))
    scene = scenes.create(
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Orbital Arrival",
        story_scope="Mauritania settles into orbit.",
        production_objective="Establish planetary scale.",
        target_runtime_seconds=60,
        setting_requirement="Xorix orbit",
        required_events=("Xorix fills the forward view",),
    )
    scene = scenes.mark_ready(scene.scene_id)
    shots = GovernedShotPlanningService(projects, scenes, ShotPlanningService(projects))
    shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Reveal Xorix",
        narrative_purpose="Reveal planetary scale.",
        production_objective="Orient the audience.",
        target_runtime_seconds=5,
        required_action="Mauritania crosses frame.",
    )

    install_planning_review_navigation()
    setattr(
        shots,
        "planning_review_service",
        GovernedPlanningReviewService.__new__(GovernedPlanningReviewService),
    )
    dialog = GovernedShotPlannerDialog(shots, scene)
    qtbot.addWidget(dialog)
    dialog.show()

    assert not hasattr(GovernedEnvironmentPlannerDialog, "_planning_review_installed")
    assert dialog.planning_review_button.text() == "Planning Review…"
    assert not dialog.planning_review_button.isEnabled()

    dialog.table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 0)
    assert dialog.planning_review_button.isEnabled()
    assert shots.plan("EP-001-SCN-001-SHT-001").status is ShotPlanStatus.DRAFT
    context.shutdown()
