"""Story-first workspace layered above the existing production hierarchy."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from vscs.application.projects import ProjectNotOpenError
from vscs.application.story import (
    StoryApprovalError,
    StoryApprovalService,
    StoryLifecycleError,
    StoryLifecycleService,
    StoryMetadata,
    StoryMetadataError,
    StoryMetadataService,
    StoryRecord,
    StorySourceType,
    StoryStatus,
    StoryStatusError,
    StoryStatusService,
)


class StoryEditorDialog(QDialog):
    """Create or edit Story identity and metadata through one guided form."""

    def __init__(
        self,
        story: StoryRecord | None = None,
        metadata: StoryMetadata | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("storyEditorDialog")
        self.setWindowTitle("Edit Story" if story else "Create Story")
        self.resize(620, 700)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit(story.title if story else "", self)
        self.title_edit.setObjectName("storyTitle")
        self.description_edit = QPlainTextEdit(story.description if story else "", self)
        self.description_edit.setObjectName("storyDescription")
        self.source_type_combo = QComboBox(self)
        self.source_type_combo.setObjectName("storySourceType")
        for source_type in StorySourceType:
            self.source_type_combo.addItem(source_type.label, source_type)
        if story is not None:
            self.source_type_combo.setCurrentIndex(
                self.source_type_combo.findData(story.source_type)
            )
        self.source_path_edit = QLineEdit(story.source_path if story else "", self)
        self.source_path_edit.setObjectName("storySourcePath")

        self.synopsis_edit = QPlainTextEdit(metadata.synopsis if metadata else "", self)
        self.synopsis_edit.setObjectName("storySynopsis")
        self.genres_edit = QLineEdit(
            ", ".join(metadata.genres) if metadata else "",
            self,
        )
        self.genres_edit.setObjectName("storyGenres")
        self.themes_edit = QLineEdit(
            ", ".join(metadata.themes) if metadata else "",
            self,
        )
        self.themes_edit.setObjectName("storyThemes")
        self.audience_edit = QLineEdit(metadata.target_audience if metadata else "", self)
        self.audience_edit.setObjectName("storyTargetAudience")
        self.language_edit = QLineEdit(metadata.language if metadata else "English", self)
        self.language_edit.setObjectName("storyLanguage")
        self.author_edit = QLineEdit(metadata.author if metadata else "", self)
        self.author_edit.setObjectName("storyAuthor")
        self.runtime_spin = QSpinBox(self)
        self.runtime_spin.setObjectName("storyEstimatedRuntime")
        self.runtime_spin.setRange(0, 100000)
        self.runtime_spin.setSpecialValueText("Not estimated")
        if metadata and metadata.estimated_runtime_minutes is not None:
            self.runtime_spin.setValue(round(metadata.estimated_runtime_minutes))
        self.keywords_edit = QLineEdit(
            ", ".join(metadata.keywords) if metadata else "",
            self,
        )
        self.keywords_edit.setObjectName("storyKeywords")
        self.notes_edit = QPlainTextEdit(metadata.notes if metadata else "", self)
        self.notes_edit.setObjectName("storyNotes")

        form.addRow("Title *", self.title_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Source type", self.source_type_combo)
        form.addRow("Source path", self.source_path_edit)
        form.addRow("Synopsis", self.synopsis_edit)
        form.addRow("Genres", self.genres_edit)
        form.addRow("Themes", self.themes_edit)
        form.addRow("Target audience", self.audience_edit)
        form.addRow("Language", self.language_edit)
        form.addRow("Author", self.author_edit)
        form.addRow("Estimated runtime (minutes)", self.runtime_spin)
        form.addRow("Keywords", self.keywords_edit)
        form.addRow("Notes", self.notes_edit)
        layout.addLayout(form)

        hint = QLabel(
            "Genres, themes and keywords may be entered as comma-separated values.",
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Story", "Story title is required.")
            self.title_edit.setFocus()
            return
        self.accept()

    @staticmethod
    def _values(text: str) -> tuple[str, ...]:
        return tuple(value.strip() for value in text.split(",") if value.strip())

    def story_values(self) -> dict[str, object]:
        """Return normalized lifecycle values from the form."""
        return {
            "title": self.title_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "source_type": self.source_type_combo.currentData(),
            "source_path": self.source_path_edit.text().strip(),
        }

    def metadata_values(self) -> dict[str, object]:
        """Return normalized metadata values from the form."""
        runtime = self.runtime_spin.value()
        return {
            "synopsis": self.synopsis_edit.toPlainText().strip(),
            "genres": self._values(self.genres_edit.text()),
            "themes": self._values(self.themes_edit.text()),
            "target_audience": self.audience_edit.text().strip(),
            "language": self.language_edit.text().strip(),
            "author": self.author_edit.text().strip(),
            "estimated_runtime_minutes": float(runtime) if runtime else None,
            "keywords": self._values(self.keywords_edit.text()),
            "notes": self.notes_edit.toPlainText().strip(),
        }


class StoryWorkspaceWidget(QWidget):
    """Manage first-class Stories while preserving the production browser."""

    def __init__(
        self,
        lifecycle: StoryLifecycleService,
        metadata: StoryMetadataService,
        statuses: StoryStatusService,
        approvals: StoryApprovalService,
        production_browser: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("storyWorkspace")
        self.lifecycle = lifecycle
        self.metadata = metadata
        self.statuses = statuses
        self.approvals = approvals
        self.production_browser = production_browser
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Story Workspace", self)
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch(1)
        self.show_archived = QCheckBox("Show archived", self)
        self.show_archived.setObjectName("showArchivedStories")
        self.show_archived.toggled.connect(self.refresh)
        header.addWidget(self.show_archived)
        self.help_button = QPushButton("Help", self)
        self.help_button.setObjectName("storyWorkspaceHelp")
        self.help_button.clicked.connect(self._show_help)
        header.addWidget(self.help_button)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        story_panel = QWidget(splitter)
        story_layout = QVBoxLayout(story_panel)
        toolbar = QHBoxLayout()
        self.new_button = self._button("New Story", "newStory", self._new_story)
        self.edit_button = self._button("Edit", "editStory", self._edit_story)
        self.duplicate_button = self._button(
            "Duplicate", "duplicateStory", self._duplicate_story
        )
        self.analyse_button = self._button(
            "Mark Analysed", "analyseStory", self._mark_analysed
        )
        self.approve_button = self._button("Approve", "approveStory", self._approve)
        self.lock_button = self._button("Lock", "lockStory", self._lock)
        self.unlock_button = self._button("Unlock", "unlockStory", self._unlock)
        self.reopen_button = self._button(
            "Reopen", "reopenStory", self._reopen
        )
        self.archive_button = self._button(
            "Archive", "archiveStory", self._archive_or_restore
        )
        for button in (
            self.new_button,
            self.edit_button,
            self.duplicate_button,
            self.analyse_button,
            self.approve_button,
            self.lock_button,
            self.unlock_button,
            self.reopen_button,
            self.archive_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        story_layout.addLayout(toolbar)

        content = QHBoxLayout()
        self.story_list = QListWidget(story_panel)
        self.story_list.setObjectName("storyList")
        self.story_list.currentItemChanged.connect(self._show_selected)
        content.addWidget(self.story_list, 1)
        self.details = QLabel(story_panel)
        self.details.setObjectName("storyWorkspaceDetails")
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.RichText)
        content.addWidget(self.details, 2)
        story_layout.addLayout(content)
        splitter.addWidget(story_panel)
        splitter.addWidget(self.production_browser)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 1)

    def _button(self, text: str, name: str, slot: object) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.clicked.connect(slot)  # type: ignore[arg-type]
        return button

    def refresh(self, *_args: object) -> None:
        """Reload Story state and the existing production hierarchy."""
        selected_id = self._selected_story_id()
        self.story_list.clear()
        try:
            stories = self.lifecycle.list_stories(
                include_archived=self.show_archived.isChecked()
            )
        except ProjectNotOpenError:
            self.details.setText("Open a project to manage Stories.")
            self._set_actions(None)
            self.production_browser.setEnabled(False)
            return
        except StoryLifecycleError as exc:
            self.details.setText(str(exc))
            self._set_actions(None)
            return
        self.production_browser.setEnabled(True)
        for story in stories:
            item = QListWidgetItem(f"{story.title}  [{story.status.label}]")
            item.setData(Qt.ItemDataRole.UserRole, story.story_id)
            self.story_list.addItem(item)
            if story.story_id == selected_id:
                self.story_list.setCurrentItem(item)
        if self.story_list.currentItem() is None and self.story_list.count():
            self.story_list.setCurrentRow(0)
        if not stories:
            self.details.setText(
                "<h3>No Story defined</h3><p>Create or import the Story before "
                "planning a Production.</p>"
            )
            self._set_actions(None)
        refresh = getattr(self.production_browser, "refresh", None)
        if callable(refresh):
            refresh()

    def _selected_story_id(self) -> str | None:
        item = self.story_list.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def _selected_story(self) -> StoryRecord | None:
        story_id = self._selected_story_id()
        return None if story_id is None else self.lifecycle.story(story_id)

    def _show_selected(self, *_args: object) -> None:
        story = self._selected_story()
        self._set_actions(story)
        if story is None:
            return
        metadata = self.metadata.metadata(story.story_id)
        completeness = self.metadata.completeness(story.story_id)
        approval = self.approvals.snapshot(story.story_id)
        synopsis = metadata.synopsis if metadata and metadata.synopsis else "Not defined"
        author = metadata.author if metadata and metadata.author else "Not defined"
        genres = ", ".join(metadata.genres) if metadata and metadata.genres else "Not defined"
        missing = ", ".join(completeness.missing_fields) or "None"
        self.details.setText(
            f"<h2>{story.title}</h2>"
            f"<p><b>ID:</b> {story.story_id}<br>"
            f"<b>Status:</b> {story.status.label}<br>"
            f"<b>Source:</b> {story.source_type.label}</p>"
            f"<h3>Story Definition</h3>"
            f"<p><b>Author:</b> {author}<br>"
            f"<b>Genres:</b> {genres}<br>"
            f"<b>Synopsis:</b> {synopsis}</p>"
            f"<h3>Readiness</h3>"
            f"<p><b>Metadata:</b> {completeness.percentage}%<br>"
            f"<b>Missing:</b> {missing}<br>"
            f"<b>Ready to approve:</b> {'Yes' if approval.can_approve else 'No'}</p>"
        )

    def _set_actions(self, story: StoryRecord | None) -> None:
        enabled = story is not None
        self.edit_button.setEnabled(enabled and not story.archived and not story.locked if story else False)
        self.duplicate_button.setEnabled(enabled)
        self.analyse_button.setEnabled(
            story is not None and story.status in {StoryStatus.DRAFT, StoryStatus.IMPORTED}
        )
        snapshot = self.approvals.snapshot(story.story_id) if story else None
        self.approve_button.setEnabled(bool(snapshot and snapshot.can_approve))
        self.lock_button.setEnabled(bool(snapshot and snapshot.can_lock))
        self.unlock_button.setEnabled(bool(snapshot and snapshot.can_unlock))
        self.reopen_button.setEnabled(bool(snapshot and snapshot.can_reopen))
        self.archive_button.setEnabled(enabled)
        self.archive_button.setText("Restore" if story and story.archived else "Archive")

    def _new_story(self) -> None:
        dialog = StoryEditorDialog(parent=self)
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
        dialog = StoryEditorDialog(story, self.metadata.metadata(story.story_id), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.lifecycle.update_story(story.story_id, **dialog.story_values())
            self.metadata.save_metadata(story.story_id, **dialog.metadata_values())
        except (ValueError, StoryLifecycleError, StoryMetadataError) as exc:
            self._error(str(exc))
        self.refresh()

    def _duplicate_story(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        try:
            duplicate = self.lifecycle.duplicate_story(story.story_id)
            metadata = self.metadata.metadata(story.story_id)
            if metadata is not None:
                values = {
                    field: getattr(metadata, field)
                    for field in (
                        "synopsis", "genres", "themes", "target_audience",
                        "language", "author", "estimated_runtime_minutes",
                        "keywords", "notes",
                    )
                }
                self.metadata.save_metadata(duplicate.story_id, **values)
        except (ValueError, StoryLifecycleError, StoryMetadataError) as exc:
            self._error(str(exc))
        self.refresh()

    def _mark_analysed(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        try:
            self.statuses.transition(
                story.story_id,
                StoryStatus.ANALYSED,
                reason="Story analysis confirmed through Story Workspace",
            )
        except (ValueError, StoryStatusError) as exc:
            self._error(str(exc))
        self.refresh()

    def _approve(self) -> None:
        self._approval_action("approve")

    def _lock(self) -> None:
        self._approval_action("lock")

    def _unlock(self) -> None:
        self._approval_action("unlock")

    def _reopen(self) -> None:
        self._approval_action("reopen")

    def _approval_action(self, action: str) -> None:
        story = self._selected_story()
        if story is None:
            return
        actor = "VSCS User"
        notes = f"Story {action} action completed through Story Workspace"
        try:
            if action == "approve":
                self.approvals.approve(story.story_id, approved_by=actor, notes=notes)
            elif action == "lock":
                self.approvals.lock(story.story_id, locked_by=actor, notes=notes)
            elif action == "unlock":
                self.approvals.unlock(story.story_id, unlocked_by=actor, notes=notes)
            else:
                self.approvals.reopen_for_revision(
                    story.story_id,
                    reopened_by=actor,
                    notes=notes,
                )
        except (ValueError, StoryApprovalError) as exc:
            self._error(str(exc))
        self.refresh()

    def _archive_or_restore(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        try:
            if story.archived:
                self.statuses.restore(
                    story.story_id,
                    reason="Story restored through Story Workspace",
                )
            else:
                self.statuses.archive(
                    story.story_id,
                    reason="Story archived through Story Workspace",
                )
        except (ValueError, StoryStatusError) as exc:
            self._error(str(exc))
        self.refresh()

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "Story Workspace Help",
            "1. Create or import a Story.\n"
            "2. Complete its metadata.\n"
            "3. Mark it Analysed after reviewing the Story structure.\n"
            "4. Approve and lock Story Canon.\n"
            "5. Use the production browser below to plan scenes and shots.\n\n"
            "Editing an analysed or approved Story returns it to an editable state. "
            "Locked Stories must be reopened or unlocked first.",
        )

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "Story Workspace", message)
