"""Qt coverage for browsing and selecting Story source files."""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from vscs.application.story import StorySourceType
from vscs.presentation.widgets.browseable_story_workspace import (
    BrowseableStoryEditorDialog,
)


def test_browse_button_selects_source_file_and_type(qtbot, monkeypatch) -> None:
    dialog = BrowseableStoryEditorDialog()
    qtbot.addWidget(dialog)

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: ("D:/Stories/Xorix.docx", "Word documents"),
    )

    dialog.browse_source_button.click()

    values = dialog.story_values()
    assert dialog.source_path_edit.text() == "D:/Stories/Xorix.docx"
    assert values["source_type"] is StorySourceType.DOCX
    assert values["source_path"] == "D:/Stories/Xorix.docx"


def test_cancelled_file_browser_preserves_existing_path(qtbot, monkeypatch) -> None:
    dialog = BrowseableStoryEditorDialog()
    qtbot.addWidget(dialog)
    dialog.source_path_edit.setText("D:/Stories/Existing.md")

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: ("", ""),
    )

    dialog.browse_source_button.click()

    assert dialog.source_path_edit.text() == "D:/Stories/Existing.md"


def test_unknown_file_extension_uses_other_source_type(qtbot, monkeypatch) -> None:
    dialog = BrowseableStoryEditorDialog()
    qtbot.addWidget(dialog)

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: ("D:/Stories/Outline.xyz", "All files"),
    )

    dialog.browse_source_button.click()

    assert dialog.story_values()["source_type"] is StorySourceType.OTHER
