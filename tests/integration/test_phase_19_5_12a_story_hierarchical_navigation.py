from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QTreeWidget, QTreeWidgetItem

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
            "Performance",
            "Environment",
            "Camera & Lighting",
            "Continuity",
            "AI Review & Gap Detection",
        ):
            _child(automation, label)

        canonical_library = _child(story, "Canonical Library")
        assert canonical_library.isExpanded()
        _child(canonical_library, "Import XPD Library…")
        _child(canonical_library, "Resolve Story Entities")
        _child(canonical_library, "Review XPD Matches…")
        _child(canonical_library, "Bind Shot Assets…")

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
            button = window.story_browser.findChild(QPushButton, object_name)
            assert button is not None
            assert button.testAttribute(hidden_attribute)

        for object_name, label in (
            ("newStory", "New Story"),
            ("editStory", "Edit"),
            ("duplicateStory", "Duplicate"),
        ):
            button = window.story_browser.findChild(QPushButton, object_name)
            assert button is not None
            assert button.text() == label


def test_phase_19_5_12_actions_are_registered_in_story_navigation(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        actions = window.story_navigation_actions
        for key in (
            "story.import_xpd",
            "story.resolve_assets",
            "story.review_xpd_matches",
            "story.bind_shot_assets",
        ):
            assert key in actions
            assert callable(actions[key])


def test_review_xpd_navigation_action_can_be_reopened_after_modal_exit(
    tmp_path: Path, qtbot
) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        tree = window.story_navigation_tree
        story = _top(tree, "Story")
        canonical_library = _child(story, "Canonical Library")
        review_item = _child(canonical_library, "Review XPD Matches…")

        invocations: list[int] = []
        window.story_navigation_actions["story.review_xpd_matches"] = lambda: invocations.append(1)

        tree.setCurrentItem(review_item)
        assert len(invocations) == 1
        assert tree.currentItem() is canonical_library

        tree.setCurrentItem(review_item)
        assert len(invocations) == 2
        assert tree.currentItem() is canonical_library
