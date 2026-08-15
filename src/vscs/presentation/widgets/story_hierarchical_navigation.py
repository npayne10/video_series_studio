"""Hierarchical Story navigation for Phase 19.5.12A.

The existing flat MainWindow navigation remains the compatibility controller so
established section indexes, View-menu actions and tests are not rewritten.  A
QTreeWidget becomes the visible dock navigation and delegates top-level section
selection back to that controller.  Story children invoke existing Story
Workspace actions; no production service or governance behaviour is duplicated.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QPushButton, QTreeWidget, QTreeWidgetItem

SECTION_ROLE = int(Qt.ItemDataRole.UserRole)
ACTION_ROLE = SECTION_ROLE + 1


def _find_button(workspace: Any, *, object_name: str = "", text: str = "") -> QPushButton | None:
    for button in workspace.findChildren(QPushButton):
        if object_name and button.objectName() == object_name:
            return button
        if text and button.text().replace("&", "").strip() == text:
            return button
    return None


def _button_action(
    window: Any,
    *,
    object_name: str = "",
    text: str = "",
    explicit: QPushButton | None = None,
) -> Callable[[], None]:
    def invoke() -> None:
        controller = window._story_flat_navigation_controller
        controller.setCurrentRow(2)
        button = explicit or _find_button(
            window.story_browser,
            object_name=object_name,
            text=text,
        )
        if button is not None and button.isEnabled():
            button.click()

    return invoke


def _story_item(parent: QTreeWidgetItem, label: str, action_key: str) -> QTreeWidgetItem:
    item = QTreeWidgetItem(parent, [label])
    item.setData(0, ACTION_ROLE, action_key)
    return item


def _hide_relocated_toolbar_actions(window: Any) -> None:
    """Leave only Story lifecycle actions in the horizontal Story toolbar."""
    relocated_object_names = {
        "generatePlanningProposals",
        "generateShotProposals",
        "resolveCanonicalAssets",
        "generatePerformanceProposals",
        "generateEnvironmentProposals",
        "generateCameraLightingProposals",
        "generateContinuityProposals",
        "reviewAutomationProposals",
        "reviewAutomationGaps",
    }
    for button in window.story_browser.findChildren(QPushButton):
        if button.objectName() in relocated_object_names or button.text().strip() == "Analyse Story":
            button.setVisible(False)

    for attribute in ("episode_planner_button", "open_in_planner_button"):
        button = getattr(window, attribute, None)
        if isinstance(button, QPushButton):
            button.setVisible(False)


def install_story_hierarchical_navigation(window: Any) -> QTreeWidget:
    """Replace the visible flat dock list with scalable hierarchical navigation."""
    existing = getattr(window, "story_navigation_tree", None)
    if isinstance(existing, QTreeWidget):
        return existing

    controller = window.navigation
    if not isinstance(controller, QListWidget):
        raise RuntimeError("Phase 19.5.12A requires the established flat navigation controller")

    # Keep the established list alive and connected.  MainWindow methods, View
    # menu actions and historical tests continue to operate against it.
    controller.setParent(window)
    controller.hide()
    window._story_flat_navigation_controller = controller

    tree = QTreeWidget(window.navigation_dock)
    tree.setObjectName("hierarchicalNavigationTree")
    tree.setHeaderHidden(True)
    tree.setMinimumWidth(250)
    window.navigation_dock.setWidget(tree)
    window.story_navigation_tree = tree

    top_level: dict[int, QTreeWidgetItem] = {}
    story_root: QTreeWidgetItem | None = None
    for index in range(controller.count()):
        source = controller.item(index)
        item = QTreeWidgetItem(tree, [source.text()])
        item.setData(0, SECTION_ROLE, index)
        top_level[index] = item
        if source.text() == "Story":
            story_root = item

    if story_root is None:
        raise RuntimeError("Story navigation section is unavailable")

    workspace_item = QTreeWidgetItem(story_root, ["Workspace"])
    workspace_item.setData(0, SECTION_ROLE, 2)
    _story_item(story_root, "Story Definition", "story.definition")

    automation = QTreeWidgetItem(story_root, ["Automation"])
    automation.setFlags(automation.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    for label, action_key in (
        ("Story Analysis", "story.analysis"),
        ("Planning Proposals", "story.planning_proposals"),
        ("Shot Proposals", "story.shot_proposals"),
        ("Canonical Asset Resolution", "story.resolve_assets"),
        ("Performance", "story.performance"),
        ("Environment", "story.environment"),
        ("Camera & Lighting", "story.camera_lighting"),
        ("Continuity", "story.continuity"),
        ("AI Review & Gap Detection", "story.review_gaps"),
    ):
        _story_item(automation, label, action_key)

    _story_item(story_root, "Proposal Review", "story.proposal_review")
    _story_item(story_root, "Production Planning", "story.production_planning")

    actions: dict[str, Callable[[], None]] = {
        "story.definition": _button_action(window, object_name="editStory"),
        "story.analysis": _button_action(window, text="Analyse Story"),
        "story.planning_proposals": _button_action(
            window, object_name="generatePlanningProposals"
        ),
        "story.shot_proposals": _button_action(window, object_name="generateShotProposals"),
        "story.resolve_assets": _button_action(window, object_name="resolveCanonicalAssets"),
        "story.performance": _button_action(window, object_name="generatePerformanceProposals"),
        "story.environment": _button_action(window, object_name="generateEnvironmentProposals"),
        "story.camera_lighting": _button_action(
            window, object_name="generateCameraLightingProposals"
        ),
        "story.continuity": _button_action(window, object_name="generateContinuityProposals"),
        "story.review_gaps": _button_action(window, object_name="reviewAutomationGaps"),
        "story.proposal_review": _button_action(window, object_name="reviewAutomationProposals"),
        "story.production_planning": _button_action(
            window, explicit=getattr(window, "episode_planner_button", None)
        ),
    }
    window.story_navigation_actions = actions

    def selected(current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        if current is None:
            return
        action_key = current.data(0, ACTION_ROLE)
        if action_key:
            action = actions.get(str(action_key))
            if action is not None:
                action()
            return
        section = current.data(0, SECTION_ROLE)
        if isinstance(section, int):
            controller.setCurrentRow(section)

    tree.currentItemChanged.connect(selected)

    def synchronize(row: int) -> None:
        item = top_level.get(row)
        if item is not None and tree.currentItem() is not item:
            tree.blockSignals(True)
            tree.setCurrentItem(item)
            tree.blockSignals(False)

    controller.currentRowChanged.connect(synchronize)
    story_root.setExpanded(True)
    automation.setExpanded(True)
    synchronize(controller.currentRow())
    _hide_relocated_toolbar_actions(window)
    return tree
