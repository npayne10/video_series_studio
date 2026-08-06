"""Story Workspace extensions for selecting an existing Story source file."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from vscs.application.story import (
    StoryLifecycleError,
    StoryMetadata,
    StoryMetadataError,
    StoryRecord,
    StorySourceType,
)

from .story_workspace import StoryEditorDialog, StoryWorkspaceWidget


class BrowseableStoryEditorDialog(StoryEditorDialog):
    """Story editor with a native file browser for the Story source path."""

    FILE_FILTER = (
        "Supported story files (*.docx *.pdf *.md *.markdown *.txt *.fdx);;"
        "Word documents (*.docx);;"
        "PDF documents (*.pdf);;"
        "Markdown files (*.md *.markdown);;"
        "Plain text files (*.txt);;"
        "Screenplay files (*.fdx);;"
        "All files (*)"
    )

    _SOURCE_TYPES: ClassVar[dict[str, StorySourceType]] = {
        ".docx": StorySourceType.DOCX,
        ".pdf": StorySourceType.PDF,
        ".md": StorySourceType.MARKDOWN,
        ".markdown": StorySourceType.MARKDOWN,
        ".txt": StorySourceType.PLAIN_TEXT,
        ".fdx": StorySourceType.SCREENPLAY,
    }

    def __init__(
        self,
        story: StoryRecord | None = None,
        metadata: StoryMetadata | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(story, metadata, parent)
        self.browse_source_button = QPushButton("Browse…", self)
        self.browse_source_button.setObjectName("browseStorySource")
        self.browse_source_button.setToolTip(
            "Browse for the manuscript, screenplay, Markdown, PDF, or text file."
        )
        self.browse_source_button.clicked.connect(self._browse_source_file)
        self._install_source_path_row()

    def _install_source_path_row(self) -> None:
        root = self.layout()
        form_item = root.itemAt(0) if root is not None else None
        form = form_item.layout() if form_item is not None else None
        if not isinstance(form, QFormLayout):
            raise RuntimeError("Story Editor form layout is unavailable.")
        row, _role = form.getWidgetPosition(self.source_path_edit)
        if row < 0:
            raise RuntimeError("Story source path field is unavailable.")
        form.removeWidget(self.source_path_edit)
        container = QWidget(self)
        container.setObjectName("storySourcePathContainer")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.source_path_edit, 1)
        layout.addWidget(self.browse_source_button)
        form.setWidget(row, QFormLayout.ItemRole.FieldRole, container)

    def _browse_source_file(self) -> None:
        current_path = self.source_path_edit.text().strip()
        start_directory = ""
        if current_path:
            current = Path(current_path)
            start_directory = str(current.parent if current.suffix else current)
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Select Story Source",
            start_directory,
            self.FILE_FILTER,
        )
        if not selected_path:
            return
        self.source_path_edit.setText(selected_path)
        source_type = self._SOURCE_TYPES.get(
            Path(selected_path).suffix.casefold(),
            StorySourceType.OTHER,
        )
        source_index = self.source_type_combo.findData(source_type)
        if source_index >= 0:
            self.source_type_combo.setCurrentIndex(source_index)


class BrowseableStoryWorkspaceWidget(StoryWorkspaceWidget):
    """Story Workspace using the browse-enabled Story editor dialog."""

    def _new_story(self) -> None:
        dialog = BrowseableStoryEditorDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            story = self.lifecycle.create_story(**dialog.story_values())
            self.metadata.save_metadata(story.story_id, **dialog.metadata_values())
        except (ValueError, StoryLifecycleError, StoryMetadataError) as exc:
            self._error(str(exc))
        self.refresh()

    def _edit_story(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        dialog = BrowseableStoryEditorDialog(
            story,
            self.metadata.metadata(story.story_id),
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.lifecycle.update_story(story.story_id, **dialog.story_values())
            self.metadata.save_metadata(story.story_id, **dialog.metadata_values())
        except (ValueError, StoryLifecycleError, StoryMetadataError) as exc:
            self._error(str(exc))
        self.refresh()
