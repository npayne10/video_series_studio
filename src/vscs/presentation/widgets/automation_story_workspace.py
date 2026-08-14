"""Typed Story Workspace extension for Phase 19.5.3 planning proposals."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout

from vscs.application.automation import (
    EpisodeSceneProposalAutomationService,
    SemanticStoryInterpretationService,
)
from vscs.application.story import StoryRecord
from vscs.application.story_analysis import (
    StoryAnalysisCacheState,
    StorySourceReader,
    StorySourceReadError,
)
from vscs.application.story_analysis.cache import StoryAnalysisCacheError
from vscs.application.story_analysis.stages import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    ANALYSIS_RESULT_ARTIFACT,
)
from vscs.domain.story_analysis import AnalysisResult, EntityResolutionResult
from vscs.infrastructure.ai import AIProviderError

from .browseable_story_workspace import BrowseableStoryWorkspaceWidget


class AutomationStoryWorkspaceWidget(BrowseableStoryWorkspaceWidget):
    """Story Workspace with explicit, non-authoritative planning automation."""

    semantic_interpretation_service: SemanticStoryInterpretationService | None = None
    episode_scene_automation_service: EpisodeSceneProposalAutomationService | None = None

    def _install_story_panel(self) -> None:
        super()._install_story_panel()
        panel = self.story_new_button.parentWidget()
        panel_layout = panel.layout() if panel is not None else None
        toolbar_item = panel_layout.itemAt(1) if isinstance(panel_layout, QVBoxLayout) else None
        toolbar = toolbar_item.layout() if toolbar_item is not None else None
        if not isinstance(toolbar, QHBoxLayout):
            raise RuntimeError("Story Workspace toolbar is unavailable.")

        self.planning_proposals_button = QPushButton("Planning Proposals…", panel)
        self.planning_proposals_button.setObjectName("generatePlanningProposals")
        self.planning_proposals_button.setToolTip(
            "Generate reviewable Episode/Scene proposals from the current analysed Story."
        )
        self.planning_proposals_button.clicked.connect(self._generate_planning_proposals)
        toolbar.insertWidget(4, self.planning_proposals_button)

    def _set_story_actions(self, story: StoryRecord | None) -> None:
        super()._set_story_actions(story)
        self.planning_proposals_button.setEnabled(story is not None and not story.archived)

    def _generate_planning_proposals(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        if self.analysis_cache is None:
            self._error("Story Analysis Cache is not registered.")
            return
        if self.semantic_interpretation_service is None:
            self._error("Semantic Story Interpretation service is not registered.")
            return
        if self.episode_scene_automation_service is None:
            self._error("Episode/Scene automation service is not registered.")
            return

        try:
            source_text = StorySourceReader().read(story)
            status = self.analysis_cache.status(story, source_text)
            if status.state is StoryAnalysisCacheState.MISSING:
                self._error("Analyse Story before generating planning proposals.")
                return
            if status.state is StoryAnalysisCacheState.STALE:
                self._error("Story Analysis is out of date. Reanalyse Story first.")
                return

            report = self.analysis_cache.load(story, source_text, allow_stale=False)
            baseline = report.artifacts.get(ANALYSIS_RESULT_ARTIFACT)
            resolution = report.artifacts.get(AI_ENTITY_RESOLUTION_ARTIFACT)
            if not isinstance(baseline, AnalysisResult):
                self._error("Cached Story Analysis does not contain the structured Story model.")
                return
            if not isinstance(resolution, EntityResolutionResult):
                self._error("Cached Story Analysis does not contain semantic entity resolution.")
                return

            semantic = self.semantic_interpretation_service.interpret(
                story_id=story.story_id,
                source_text=source_text,
                source_revision=status.current_revision,
                baseline=baseline,
                entity_resolution=resolution,
            )
            proposals = self.episode_scene_automation_service.generate(
                story_id=story.story_id,
                source_text=source_text,
                source_revision=status.current_revision,
                baseline=baseline,
                semantic=semantic,
            )
        except (
            StoryAnalysisCacheError,
            StorySourceReadError,
            AIProviderError,
            ValueError,
        ) as exc:
            self._error(str(exc))
            return

        episodes = sum(1 for item in proposals if item.proposal_type.value == "episode")
        scenes = sum(1 for item in proposals if item.proposal_type.value == "scene")
        QMessageBox.information(
            self,
            "Planning Proposals Generated",
            f"Generated {episodes} Episode proposal(s) and {scenes} Scene proposal(s).\n\n"
            "These are reviewable automation proposals only. No Episode or Scene has been "
            "created, marked Ready, or approved in Production Planning.",
        )
