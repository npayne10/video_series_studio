"""Consolidate Story Workspace production planning into one authoritative environment."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTreeWidgetItem

from vscs.application.story import (
    EpisodePlanningService,
    GovernedShotPlanningService,
    ScenePlanningService,
)

from .episode_planner import EpisodePlannerDialog
from .governed_shot_planner import GovernedShotPlannerDialog
from .scene_planner import ScenePlannerDialog

EPISODE_KIND = "episode_plan"
SCENE_KIND = "scene_plan"
SHOT_KIND = "shot_plan"
LEGACY_ACTIONS = (
    "new_button",
    "edit_button",
    "delete_button",
    "plan_button",
    "shot_planner_button",
    "acpp_button",
)


def install_production_planning_workspace(
    workspace: Any,
    episode_service: EpisodePlanningService,
    scene_service: ScenePlanningService,
    shot_service: GovernedShotPlanningService | None = None,
) -> QPushButton:
    """Make governed Episode/Scene/Shot planners the only authoritative planning path."""
    if getattr(workspace, "_production_planning_consolidated", False):
        existing_button = getattr(workspace, "open_in_planner_button", None)
        if isinstance(existing_button, QPushButton):
            return existing_button
        raise RuntimeError("Consolidated planning workspace has no navigation button")

    workspace.episode_planning_service = episode_service
    workspace.scene_planning_service = scene_service
    workspace.governed_shot_planning_service = shot_service
    _disable_legacy_actions(workspace)

    workspace.refresh_button.setText("Refresh Overview")
    workspace.refresh_button.setToolTip("Refresh the governed production-planning overview")
    workspace.search_edit.setPlaceholderText("Search governed episode, scene or shot plans...")

    toolbar = _production_toolbar(workspace)
    open_button = QPushButton("Open in Planner", workspace)
    open_button.setObjectName("openAuthoritativePlanner")
    open_button.setToolTip("Open the authoritative planner for the selected Episode, Scene or Shot")
    open_button.setEnabled(False)
    toolbar.insertWidget(max(0, toolbar.indexOf(workspace.refresh_button)), open_button)
    workspace.open_in_planner_button = open_button

    original_refresh: Callable[..., None] = workspace.refresh

    def consolidated_refresh(*args: object, **kwargs: object) -> None:
        original_refresh(*args, **kwargs)
        _refresh_authoritative_overview(workspace, episode_service, scene_service, shot_service)

    workspace.refresh = consolidated_refresh

    with suppress(RuntimeError, TypeError):
        workspace.refresh_button.clicked.disconnect()
    workspace.refresh_button.clicked.connect(consolidated_refresh)

    with suppress(RuntimeError, TypeError):
        workspace.show_archived.toggled.disconnect(original_refresh)
    workspace.show_archived.toggled.connect(consolidated_refresh)

    workspace.story_list.currentItemChanged.connect(
        lambda _current, _previous: _refresh_authoritative_overview(
            workspace,
            episode_service,
            scene_service,
            shot_service,
        )
    )
    workspace.tree.currentItemChanged.connect(
        lambda current, _previous: _show_authoritative_selection(
            workspace,
            episode_service,
            scene_service,
            shot_service,
            current,
        )
    )
    workspace.tree.itemDoubleClicked.connect(lambda _item, _column: _open_selected(workspace))
    open_button.clicked.connect(lambda: _open_selected(workspace))

    workspace._open_authoritative_planner = lambda: _open_selected(workspace)
    workspace._production_planning_consolidated = True
    consolidated_refresh()
    return open_button


def _disable_legacy_actions(workspace: Any) -> None:
    for name in LEGACY_ACTIONS:
        button = getattr(workspace, name, None)
        if button is not None:
            button.hide()
            button.setEnabled(False)


def _production_toolbar(workspace: Any) -> QHBoxLayout:
    root = workspace.layout()
    if root is None:
        raise RuntimeError("Story Workspace layout is unavailable")
    for index in range(root.count()):
        item = root.itemAt(index)
        layout = item.layout() if item is not None else None
        if not isinstance(layout, QHBoxLayout):
            continue
        for child_index in range(layout.count()):
            layout_item = layout.itemAt(child_index)
            if layout_item is None:
                continue
            if layout_item.widget() is workspace.refresh_button:
                return layout
    raise RuntimeError("Production overview toolbar is unavailable")


def _refresh_authoritative_overview(
    workspace: Any,
    episodes: EpisodePlanningService,
    scenes: ScenePlanningService,
    shots: GovernedShotPlanningService | None,
) -> None:
    _disable_legacy_actions(workspace)
    story = workspace._selected_story()
    workspace.tree.clear()
    workspace.details.clear()
    workspace.open_in_planner_button.setEnabled(False)

    if story is None:
        workspace.empty_label.setText("Select a Story to view governed production planning.")
        workspace.empty_label.show()
        _update_dashboard(workspace, (), (), ())
        return

    episode_plans = episodes.list_plans(story_id=story.story_id)
    scene_plans = tuple(
        scene
        for episode in episode_plans
        for scene in scenes.list_plans(episode_id=episode.episode_id)
    )
    shot_plans = (
        tuple(shot for scene in scene_plans for shot in shots.list_plans(scene_id=scene.scene_id))
        if shots is not None
        else ()
    )
    by_episode: dict[str, list[Any]] = {}
    by_scene: dict[str, list[Any]] = {}
    for scene in scene_plans:
        by_episode.setdefault(scene.episode_id, []).append(scene)
    for shot in shot_plans:
        by_scene.setdefault(shot.scene_id, []).append(shot)

    for episode in episode_plans:
        episode_item = QTreeWidgetItem(
            (
                f"{episode.episode_id} — {episode.title}",
                "Episode Plan",
                episode.status.value.title(),
                _duration(episode.target_runtime_seconds),
                "—",
            )
        )
        episode_item.setData(0, Qt.ItemDataRole.UserRole, (EPISODE_KIND, episode.episode_id))
        workspace.tree.addTopLevelItem(episode_item)

        for scene in sorted(
            by_episode.get(episode.episode_id, []), key=lambda item: item.sequence_number
        ):
            status = scene.status.value.title()
            if not scenes.is_upstream_current(scene):
                status = f"{status} / Stale"
            scene_item = QTreeWidgetItem(
                (
                    f"{scene.scene_id} — {scene.title}",
                    "Scene Plan",
                    status,
                    _duration(scene.target_runtime_seconds),
                    "—",
                )
            )
            scene_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                (SCENE_KIND, scene.scene_id, episode.episode_id),
            )
            episode_item.addChild(scene_item)

            for shot in sorted(
                by_scene.get(scene.scene_id, []), key=lambda item: item.sequence_number
            ):
                shot_status = shot.status.value.title()
                if shots is not None and not shots.is_upstream_current(shot):
                    shot_status = f"{shot_status} / Stale"
                shot_item = QTreeWidgetItem(
                    (
                        f"{shot.shot_id} — {shot.title}",
                        "Shot Plan",
                        shot_status,
                        _duration(shot.target_runtime_seconds),
                        "—",
                    )
                )
                shot_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    (SHOT_KIND, shot.shot_id, scene.scene_id),
                )
                scene_item.addChild(shot_item)

    workspace.tree.expandAll()
    workspace.empty_label.setVisible(not episode_plans)
    workspace.empty_label.setText(
        "No governed production plan yet. Use Production Planning… to create the first Episode Plan."
    )
    _update_dashboard(workspace, episode_plans, scene_plans, shot_plans)
    workspace._apply_filters()
    if workspace.tree.currentItem() is None and workspace.tree.topLevelItemCount():
        workspace.tree.setCurrentItem(workspace.tree.topLevelItem(0))


def _update_dashboard(
    workspace: Any,
    episodes: tuple[Any, ...],
    scenes: tuple[Any, ...],
    shots: tuple[Any, ...],
) -> None:
    ready_items = sum(1 for item in (*scenes, *shots) if item.status.value == "ready")
    draft_items = sum(1 for item in (*scenes, *shots) if item.status.value == "draft")
    duration = sum(scene.target_runtime_seconds for scene in scenes)
    values = {
        "containers": str(len(episodes)),
        "scenes": str(len(scenes)),
        "shots": str(len(shots)),
        "planned": str(len(scenes) + len(shots)),
        "ready": str(ready_items),
        "draft": str(draft_items),
        "duration": _duration(duration),
        "assets": "0",
    }
    for key, value in values.items():
        workspace.dashboard_labels[key].setText(value)


def _show_authoritative_selection(
    workspace: Any,
    episodes: EpisodePlanningService,
    scenes: ScenePlanningService,
    shots: GovernedShotPlanningService | None,
    current: QTreeWidgetItem | None,
) -> None:
    if current is None:
        workspace.open_in_planner_button.setEnabled(False)
        return
    data = current.data(0, Qt.ItemDataRole.UserRole)
    if not data:
        workspace.open_in_planner_button.setEnabled(False)
        return

    kind = str(data[0])
    workspace.open_in_planner_button.setEnabled(
        kind in {EPISODE_KIND, SCENE_KIND} or (kind == SHOT_KIND and shots is not None)
    )
    if kind == EPISODE_KIND:
        episode = episodes.plan(str(data[1]))
        if episode is None:
            return
        workspace.details.setHtml(
            f"<h2>{episode.title}</h2>"
            f"<p><b>ID:</b> {episode.episode_id}</p>"
            f"<p><b>Status:</b> {episode.status.value.title()}</p>"
            f"<p><b>Runtime target:</b> {_duration(episode.target_runtime_seconds)}</p>"
            f"<p><b>Story scope:</b> {episode.story_scope}</p>"
            f"<p><b>Production objective:</b> {episode.production_objective}</p>"
            "<p><i>Edit this plan only through Production Planning.</i></p>"
        )
        return

    if kind == SCENE_KIND:
        scene = scenes.plan(str(data[1]))
        if scene is None:
            return
        status = scene.status.value.title()
        if not scenes.is_upstream_current(scene):
            status = f"{status} / Stale"
        workspace.details.setHtml(
            f"<h2>{scene.title}</h2>"
            f"<p><b>ID:</b> {scene.scene_id}</p>"
            f"<p><b>Status:</b> {status}</p>"
            f"<p><b>Runtime target:</b> {_duration(scene.target_runtime_seconds)}</p>"
            f"<p><b>Setting requirement:</b> {scene.setting_requirement}</p>"
            f"<p><b>Story scope:</b> {scene.story_scope}</p>"
            f"<p><b>Production objective:</b> {scene.production_objective}</p>"
            "<p><i>Edit this plan only through the Scene Planner.</i></p>"
        )
        return

    if kind == SHOT_KIND and shots is not None:
        shot = shots.plan(str(data[1]))
        if shot is None:
            return
        status = shot.status.value.title()
        if not shots.is_upstream_current(shot):
            status = f"{status} / Stale"
        workspace.details.setHtml(
            f"<h2>{shot.title}</h2>"
            f"<p><b>ID:</b> {shot.shot_id}</p>"
            f"<p><b>Status:</b> {status}</p>"
            f"<p><b>Runtime target:</b> {_duration(shot.target_runtime_seconds)}</p>"
            f"<p><b>Narrative purpose:</b> {shot.narrative_purpose}</p>"
            f"<p><b>Required action:</b> {shot.required_action}</p>"
            f"<p><b>Production objective:</b> {shot.production_objective}</p>"
            "<p><i>Edit this plan only through the Shot Planner.</i></p>"
        )


def _open_selected(workspace: Any) -> None:
    current = workspace.tree.currentItem()
    story = workspace._selected_story()
    if current is None or story is None:
        return
    data = current.data(0, Qt.ItemDataRole.UserRole)
    if not data:
        return

    kind = str(data[0])
    episodes: EpisodePlanningService = workspace.episode_planning_service
    scenes: ScenePlanningService = workspace.scene_planning_service
    shots: GovernedShotPlanningService | None = workspace.governed_shot_planning_service
    if kind == EPISODE_KIND:
        episode_dialog = EpisodePlannerDialog(episodes, story, workspace, scene_service=scenes)
        _select_table_identity(episode_dialog.table, str(data[1]))
        episode_dialog.exec()
        workspace.refresh()
        return

    if kind == SCENE_KIND:
        episode = episodes.plan(str(data[2]))
        if episode is None:
            return
        scene_dialog = ScenePlannerDialog(scenes, episode, workspace)
        _select_table_identity(scene_dialog.table, str(data[1]))
        scene_dialog.exec()
        workspace.refresh()
        return

    if kind == SHOT_KIND and shots is not None:
        scene = scenes.plan(str(data[2]))
        if scene is None:
            return
        shot_dialog = GovernedShotPlannerDialog(shots, scene, workspace)
        shot_dialog._select_identity(str(data[1]))
        shot_dialog.exec()
        workspace.refresh()


def _select_table_identity(table: Any, identity: str) -> None:
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item is not None and item.text() == identity:
            table.selectRow(row)
            return


def _duration(seconds: int | float) -> str:
    total = round(seconds)
    minutes, remainder = divmod(total, 60)
    return f"{minutes}:{remainder:02d}"
