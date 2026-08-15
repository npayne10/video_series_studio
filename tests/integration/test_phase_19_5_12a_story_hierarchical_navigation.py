from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from vscs.application.projects import ProjectService
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


def _child(parent: QTreeWidgetItem, label: str) -> QTreeWidgetItem:
    for index in range(parent.childCount()):
        item = parent.child(index)
        if item.text(0) == label:
            return item
    raise AssertionError(f"Navigation item not found: {label}")


def _top(tree: QTreeWidget, label: str) -> QTreeWidgetItem:
    for index in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(index)
        if item.text(0) == label:
            return item
    raise AssertionError(f"Top-level navigation item not found: {label}")


def test_story_navigation_is_hierarchical_and_complete(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        tree = window.story_navigation_tree
        assert isinstance(tree, QTreeWidget)
        story = _top(tree, "Story")
        assert story.isExpanded()
        _child(story, "Workspace")
        _child(story, "Story Definition")
        automation = _child(story, "Automation")
        assert automation.isExpanded()
        for label in (
            "Story Analysis",
            "Planning Proposals",
            "Shot Proposals",
            "Canonical Asset Resolution",
            "Performance",
            "Environment",
            "Camera & Lighting",
            "Continuity",
            "AI Review & Gap Detection",
        ):
            _child(automation, label)
        _child(story, "Proposal Review")
        _child(story, "Production Planning")


def test_relocated_story_actions_are_removed_from_horizontal_toolbar(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        hidden_attribute = Qt.WidgetAttribute.WA_WState_Hidden
        for object_name in (
            "generatePlanningProposals",
            "generateShotProposals",
            "resolveCanonicalAssets",
            "generatePerformanceProposals",
            "generateEnvironmentProposals",
            "generateCameraLightingProposals",
            "generateContinuityProposals",
            "reviewAutomationProposals",
            "reviewAutomationGaps",
        ):
            button = window.story_browser.findChild(
                type(window.story_browser.new_button), object_name
            )
            assert button is not None
            assert button.testAttribute(hidden_attribute)

        assert not window.story_browser.new_button.testAttribute(hidden_attribute)
        assert not window.story_browser.edit_button.testAttribute(hidden_attribute)
        assert not window.story_browser.duplicate_button.testAttribute(hidden_attribute)
