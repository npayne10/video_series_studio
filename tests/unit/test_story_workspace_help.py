"""Qt coverage for comprehensive Story Workspace help."""

from __future__ import annotations

from vscs.presentation.help import StoryWorkspaceHelpDialog


def test_story_workspace_help_contains_required_sections(qtbot) -> None:
    dialog = StoryWorkspaceHelpDialog()
    qtbot.addWidget(dialog)

    titles = [
        dialog.section_list.item(index).text()
        for index in range(dialog.section_list.count())
    ]

    assert titles == [
        "Overview",
        "Story Lifecycle",
        "Story Metadata",
        "Story Governance",
        "Source Files",
        "Production Workflow",
        "Best Practices",
        "Physical Reality",
        "Related Workspaces",
    ]


def test_story_workspace_help_displays_workflow_and_physical_reality(qtbot) -> None:
    dialog = StoryWorkspaceHelpDialog()
    qtbot.addWidget(dialog)

    dialog.section_list.setCurrentRow(5)
    assert "Story Analysis" in dialog.content.toPlainText()
    assert "Production Planning" in dialog.content.toPlainText()
    assert "Release" in dialog.content.toPlainText()

    dialog.section_list.setCurrentRow(7)
    text = dialog.content.toPlainText()
    assert "gravity" in text.casefold()
    assert "inertia" in text.casefold()
    assert "Earth gravity remains 1G" in text


def test_story_workspace_help_is_available_without_story_state(qtbot) -> None:
    dialog = StoryWorkspaceHelpDialog()
    qtbot.addWidget(dialog)

    assert dialog.objectName() == "storyWorkspaceHelpDialog"
    assert dialog.section_list.currentRow() == 0
    assert "starting point" in dialog.content.toPlainText()
