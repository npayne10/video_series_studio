"""Story Workspace extensions for selecting and analysing Story source files."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QWidget,
)

from vscs.application.story import (
    StoryLifecycleError,
    StoryMetadata,
    StoryMetadataError,
    StoryRecord,
    StorySourceType,
    StoryStatus,
    StoryStatusError,
)
from vscs.application.story_analysis import (
    ApprovedStoryIntelligenceService,
    CachedStoryAnalysisEngine,
    StoryAnalysisCacheError,
    StoryAnalysisCacheService,
    StoryAnalysisCacheState,
    StoryAnalysisEngine,
    StoryIntelligenceDashboardService,
    StorySourceReadError,
    StorySourceReader,
)
from vscs.presentation.help import StoryWorkspaceHelpDialog

from .story_ai_entity_review import AIEntityReviewDialog
from .story_analysis_workspace import StoryAnalysisWorkspaceDialog
from .story_intelligence_dashboard import StoryIntelligenceDashboardDialog
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
        source_index = self.source_type_combo.findData(source_type.value)
        if source_index >= 0:
            self.source_type_combo.setCurrentIndex(source_index)

    def story_values(self) -> dict[str, object]:
        """Return lifecycle values with a strongly typed Story source type."""
        values = super().story_values()
        values["source_type"] = StorySourceType(str(values["source_type"]))
        return values


class BrowseableStoryWorkspaceWidget(StoryWorkspaceWidget):
    """Story Workspace with explicit analysis execution and cache-only review surfaces."""

    analysis_engine: StoryAnalysisEngine | None = None
    analysis_cache: StoryAnalysisCacheService | None = None
    intelligence_service: ApprovedStoryIntelligenceService | None = None

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

    def _set_story_actions(self, story: StoryRecord | None) -> None:
        super()._set_story_actions(story)
        self.analyse_button.setText("Analyse Story")
        self.analyse_button.setEnabled(story is not None and not story.archived)

    def _mark_analysed(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        if self.analysis_cache is None:
            self._error("Story Analysis Cache is not registered.")
            return
        try:
            source_text = StorySourceReader().read(story)
            status = self.analysis_cache.status(story, source_text)
        except (StorySourceReadError, StoryAnalysisCacheError) as exc:
            self._error(str(exc))
            return

        if status.state is StoryAnalysisCacheState.MISSING:
            if not self._run_analysis(story, source_text):
                return
        elif status.state is StoryAnalysisCacheState.STALE:
            answer = QMessageBox.question(
                self,
                "Story Analysis Out of Date",
                "The Story has changed since the last analysis.\n\n"
                "Reanalyse now? This may call the configured AI provider.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer is QMessageBox.StandardButton.Yes and not self._run_analysis(
                story, source_text
            ):
                return

        cached_engine = CachedStoryAnalysisEngine(self.analysis_cache, story)
        dialog = StoryAnalysisWorkspaceDialog(story, cached_engine, parent=self)
        dialog.analyse_button.setText("Reload Cached Analysis")
        dialog.graph_button.setText("Reload Cached Graph")
        dialog.refresh_button.setText("Reload Cached")
        self._install_ai_review_action(dialog, story)
        self._install_intelligence_dashboard_action(dialog, story)
        self._install_reanalyse_action(dialog, story, source_text)
        self._story_analysis_dialog = dialog
        dialog.exec()
        if dialog.analysis is None:
            return
        if story.status in {StoryStatus.DRAFT, StoryStatus.IMPORTED}:
            try:
                self.statuses.transition(
                    story.story_id,
                    StoryStatus.ANALYSED,
                    reason="Story Analysis pipeline completed and was reviewed",
                )
            except (ValueError, StoryStatusError) as exc:
                self._error(str(exc))
        self.refresh()

    def _run_analysis(self, story: StoryRecord, source_text: str) -> bool:
        if self.analysis_cache is None:
            return False
        try:
            report = self.analysis_cache.analyze(story, source_text)
        except StoryAnalysisCacheError as exc:
            self._error(str(exc))
            return False
        if report.status.value != "completed":
            self._error("\n".join(report.diagnostics) or "Story Analysis failed.")
            return False
        return True

    def _analysis_toolbar(self, dialog: StoryAnalysisWorkspaceDialog) -> QHBoxLayout:
        root = dialog.layout()
        toolbar_item = root.itemAt(0) if root is not None else None
        toolbar = toolbar_item.layout() if toolbar_item is not None else None
        if not isinstance(toolbar, QHBoxLayout):
            raise RuntimeError("Story Analysis toolbar is unavailable.")
        return toolbar

    def _install_ai_review_action(
        self,
        dialog: StoryAnalysisWorkspaceDialog,
        story: StoryRecord,
    ) -> None:
        toolbar = self._analysis_toolbar(dialog)
        button = QPushButton("Review AI Entities", dialog)
        button.setObjectName("reviewAIStoryEntities")
        button.setToolTip("Review cached AI-proposed production entities without rerunning AI.")
        button.clicked.connect(lambda: self._review_ai_entities(story, dialog))
        toolbar.insertWidget(3, button)
        dialog.ai_review_button = button

    def _install_intelligence_dashboard_action(
        self,
        dialog: StoryAnalysisWorkspaceDialog,
        story: StoryRecord,
    ) -> None:
        toolbar = self._analysis_toolbar(dialog)
        button = QPushButton("Story Intelligence", dialog)
        button.setObjectName("openStoryIntelligenceDashboard")
        button.setToolTip("Open cached production-readiness metrics without rerunning AI.")
        button.clicked.connect(lambda: self._show_story_intelligence(story, dialog))
        toolbar.insertWidget(4, button)
        dialog.story_intelligence_button = button

    def _install_reanalyse_action(
        self,
        dialog: StoryAnalysisWorkspaceDialog,
        story: StoryRecord,
        source_text: str,
    ) -> None:
        toolbar = self._analysis_toolbar(dialog)
        button = QPushButton("Reanalyse Story", dialog)
        button.setObjectName("reanalyseStoryExplicit")
        button.setToolTip("Explicitly rerun Story Analysis and the configured AI provider.")
        button.clicked.connect(
            lambda: self._reanalyse_from_dialog(story, source_text, dialog)
        )
        toolbar.insertWidget(5, button)
        dialog.reanalyse_story_button = button

    def _reanalyse_from_dialog(
        self,
        story: StoryRecord,
        source_text: str,
        dialog: StoryAnalysisWorkspaceDialog,
    ) -> None:
        answer = QMessageBox.question(
            dialog,
            "Reanalyse Story",
            "Run Story Analysis again? This may call the configured AI provider.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            current_source = StorySourceReader().read(story)
        except StorySourceReadError as exc:
            self._error(str(exc))
            return
        if self._run_analysis(story, current_source):
            dialog.rebuild_analysis()

    def _cached_engine(self, story: StoryRecord) -> CachedStoryAnalysisEngine | None:
        if self.analysis_cache is None:
            self._error("Story Analysis Cache is not registered.")
            return None
        return CachedStoryAnalysisEngine(self.analysis_cache, story)

    def _review_ai_entities(
        self,
        story: StoryRecord,
        parent: QWidget | None = None,
    ) -> None:
        engine = self._cached_engine(story)
        if engine is None:
            return
        self._ai_entity_review_dialog = AIEntityReviewDialog(
            story,
            engine,
            parent=parent or self,
            intelligence=self.intelligence_service,
        )
        self._ai_entity_review_dialog.refresh_button.setText("Reload Cached Analysis")
        self._ai_entity_review_dialog.exec()

    def _show_story_intelligence(
        self,
        story: StoryRecord,
        parent: QWidget | None = None,
    ) -> None:
        engine = self._cached_engine(story)
        if engine is None:
            return
        if self.intelligence_service is None:
            self._error("Approved Story Intelligence service is not registered.")
            return
        dashboard = StoryIntelligenceDashboardService(
            self.intelligence_service.assets,
            self.intelligence_service,
            self.metadata,
        )
        self._story_intelligence_dashboard = StoryIntelligenceDashboardDialog(
            story,
            engine,
            dashboard,
            parent=parent or self,
            review_callback=lambda: self._review_ai_entities(
                story,
                self._story_intelligence_dashboard,
            ),
        )
        self._story_intelligence_dashboard.refresh_button.setText("Reload Cached Dashboard")
        self._story_intelligence_dashboard.exec()

    def _show_help(self) -> None:
        self._story_help_dialog = StoryWorkspaceHelpDialog(self)
        self._story_help_dialog.show()
        self._story_help_dialog.raise_()
        self._story_help_dialog.activateWindow()
