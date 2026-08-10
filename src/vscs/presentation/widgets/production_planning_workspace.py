"""Consolidate Story Workspace production planning into one authoritative environment."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTreeWidgetItem

from vscs.application.story import EpisodePlanningService, ScenePlanningService

from .episode_planner import EpisodePlannerDialog
from .scene_planner import ScenePlannerDialog

EPISODE_KIND = "episode_plan"
SCENE_KIND = "scene_plan"
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
) -> QPushButton:
    """Make governed Episode/Scene planners the only authoritative planning path."""
    if getattr(workspace, "_production_planning_consolidated", False):
        return workspace.open_in_planner_button

    workspace.episode_planning_service = episode_service
    workspace.scene_planning_service = scene_service
    _disable_legacy_actions(workspace)

    workspace.refresh_button.setText("Refresh Overview")
    workspace.refresh_button.setToolTip("Refresh the governed production-planning overview")
    workspace.search_edit.setPlaceholderText("Search governed episode or scene plans...")

    toolbar = _production_toolbar(workspace)
    open_button = QPushButton("Open in Planner", workspace)
    open_button.setObjectName("openAuthoritativePlanner")
    open_button.setToolTip("Open the authoritative planner for the selected Episode or Scene")
    open_button.setEnabled(False)
    toolbar.insertWidget(max(0, toolbar.indexOf(workspace.refresh_button)), open_button)
    workspace.open_in_planner_button = open_button

    original_refresh: Callable[..., None] = workspace.refresh

    def consolidated_refresh(*args: object, **kwargs: object) -> None:
        original_refresh(*args, **kwargs)
        _refresh_authoritative_overview(workspace, episode_service, scene_service)

    workspace.refresh = consolidated_refresh

    with suppress(RuntimeError, TypeError):
        workspace.refresh_button.clicked.disconnect()
    workspace.refresh_button.clicked.connect(consolidated_refresh)

    with suppress(RuntimeError, TypeError):
        workspace.show_archived.toggled.disconnect(original_refresh)
    workspace.show_archived.toggled.connect(consolidated_refresh)

    workspace.story_list.currentItemChanged.connect(
        lambda _current, _previous: _refresh_authoritative_overview(
            workspace, episode_service, scene_service
        )
    )
    workspace.tree.currentItemChanged.connect(
        lambda current, _previous: _show_authoritative_selection(
            workspace, episode_service, scene_service, current
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
            child = layout.itemAt(child_index).widget()
            if child is workspace.refresh_button:
                return layout
    raise RuntimeError("Production overview toolbar is unavailable")


def _refresh_authoritative_overview(
    workspace: Any,
    episodes: EpisodePlanningService,
    scenes: ScenePlanningService,
) -> None:
    _disable_legacy_actions(workspace)
    story = workspace._selected_story()
    workspace.tree.clear()
    workspace.details.clear()
    workspace.open_in_planner_button.setEnabled(False)

    if story is None:
        workspace.empty_label.setText("Select a Story to view governed production planning.")
        workspace.empty_label.show()
        _update_dashboard(workspace, (), ())
        return

    episode_plans = episodes.list_plans(story_id=story.story_id)
    scene_plans = tuple(
        scene
        for episode in episode_plans
        for scene in scenes.list_plans(episode_id=episode.episode_id)
    )
    by_episode: dict[str, list[Any]] = {}
    for scene in scene_plans:
        by_episode.setdefault(scene.episode_id, []).append(scene)

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
        episode_item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            (EPISODE_KIND, episode.episode_id),
        )
        workspace.tree.addTopLevelItem(episode_item)

        for scene in sorted(by_episode.get(episode.episode_id, []), key=lambda item: item.sequence_number):
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

    workspace.tree.expandAll()
    workspace.empty_label.setVisible(not episode_plans)
    workspace.empty_label.setText(
        "No governed production plan yet. Use Production Planning… to create the first Episode Plan."
    )
    _update_dashboard(workspace, episode_plans, scene_plans)
    workspace._apply_filters()
    if workspace.tree.currentItem() is None and workspace.tree.topLevelItemCount():
        workspace.tree.setCurrentItem(workspace.tree.topLevelItem(0))


def _update_dashboard(workspace: Any, episodes: tuple[Any, ...], scenes: tuple[Any, ...]) -> None:
    ready_scenes = sum(1 for scene in scenes if scene.status.value == "ready")
    draft_scenes = sum(1 for scene in scenes if scene.status.value == "draft")
    duration = sum(scene.target_runtime_seconds for scene in scenes)
    values = {
        "containers": str(len(episodes)),
        "scenes": str(len(scenes)),
        "shots": "0",
        "planned": str(len(scenes)),
        "ready": str(ready_scenes),
        "draft": str(draft_scenes),
        "duration": _duration(duration),
        "assets": "0",
    }
    for key, value in values.items():
        workspace.dashboard_labels[key].setText(value)


def _show_authoritative_selection(
    workspace: Any,
    episodes: EpisodePlanningService,
    scenes: ScenePlanningService,
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
    workspace.open_in_planner_button.setEnabled(kind in {EPISODE_KIND, SCENE_KIND})
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
    if kind == EPISODE_KIND:
        dialog = EpisodePlannerDialog(episodes, story, workspace, scene_service=scenes)
        _select_table_identity(dialog.table, str(data[1]))
        dialog.exec()
        workspace.refresh()
        return

    if kind == SCENE_KIND:
        episode = episodes.plan(str(data[2]))
        if episode is None:
            return
        dialog = ScenePlannerDialog(scenes, episode, workspace)
        _select_table_identity(dialog.table, str(data[1]))
        dialog.exec()
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
