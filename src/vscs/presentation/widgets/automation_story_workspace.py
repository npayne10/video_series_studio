"""Typed Story Workspace extension for governed Phase 19.5 planning proposals."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout

from vscs.application.automation import (
    AutomationProposalService,
    CanonicalEntityAssetResolutionAutomationService,
    EpisodeSceneProposalAutomationService,
    SceneShotProposalAutomationService,
    SemanticStoryInterpretationService,
)
from vscs.application.story import StoryRecord
from vscs.application.story_analysis import (
    AssetServiceStoryEntityCatalog,
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
from vscs.presentation.dialogs.automation_proposal_review_dialog import (
    AutomationProposalReviewDialog,
)

from .browseable_story_workspace import BrowseableStoryWorkspaceWidget


class AutomationStoryWorkspaceWidget(BrowseableStoryWorkspaceWidget):
    """Story Workspace with explicit, non-authoritative planning automation."""

    semantic_interpretation_service: SemanticStoryInterpretationService | None = None
    episode_scene_automation_service: EpisodeSceneProposalAutomationService | None = None
    scene_shot_automation_service: SceneShotProposalAutomationService | None = None
    canonical_entity_asset_automation_service: (
        CanonicalEntityAssetResolutionAutomationService | None
    ) = None

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

        self.shot_proposals_button = QPushButton("Shot Proposals…", panel)
        self.shot_proposals_button.setObjectName("generateShotProposals")
        self.shot_proposals_button.setToolTip(
            "Generate reviewable Shot proposals from the current Scene proposals."
        )
        self.shot_proposals_button.clicked.connect(self._generate_shot_proposals)
        toolbar.insertWidget(5, self.shot_proposals_button)

        self.resolve_assets_button = QPushButton("Resolve Assets…", panel)
        self.resolve_assets_button.setObjectName("resolveCanonicalAssets")
        self.resolve_assets_button.setToolTip(
            "Resolve Story entities against current XPD, CAP and canonical-reference truth."
        )
        self.resolve_assets_button.clicked.connect(self._resolve_assets)
        toolbar.insertWidget(6, self.resolve_assets_button)

        self.review_proposals_button = QPushButton("Review Proposals…", panel)
        self.review_proposals_button.setObjectName("reviewAutomationProposals")
        self.review_proposals_button.setToolTip(
            "Inspect current Story automation proposals without rerunning automation."
        )
        self.review_proposals_button.clicked.connect(self._review_proposals)
        toolbar.insertWidget(7, self.review_proposals_button)

    def _set_story_actions(self, story: StoryRecord | None) -> None:
        super()._set_story_actions(story)
        enabled = story is not None and not story.archived
        self.planning_proposals_button.setEnabled(enabled)
        self.shot_proposals_button.setEnabled(enabled)
        self.resolve_assets_button.setEnabled(enabled)
        self.review_proposals_button.setEnabled(enabled)

    def _current_analysis(self, story: StoryRecord) -> tuple[str, str, AnalysisResult] | None:
        if self.analysis_cache is None:
            self._error("Story Analysis Cache is not registered.")
            return None
        try:
            source_text = StorySourceReader().read(story)
            status = self.analysis_cache.status(story, source_text)
            if status.state is StoryAnalysisCacheState.MISSING:
                self._error("Analyse Story before generating automation proposals.")
                return None
            if status.state is StoryAnalysisCacheState.STALE:
                self._error("Story Analysis is out of date. Reanalyse Story first.")
                return None
            report = self.analysis_cache.load(story, source_text, allow_stale=False)
        except (StoryAnalysisCacheError, StorySourceReadError) as exc:
            self._error(str(exc))
            return None

        baseline = report.artifacts.get(ANALYSIS_RESULT_ARTIFACT)
        if not isinstance(baseline, AnalysisResult):
            self._error("Cached Story Analysis does not contain the structured Story model.")
            return None
        return source_text, status.current_revision, baseline

    def _current_entity_resolution(
        self,
        story: StoryRecord,
        source_text: str,
    ) -> EntityResolutionResult | None:
        if self.analysis_cache is None:
            self._error("Story Analysis Cache is not registered.")
            return None
        try:
            report = self.analysis_cache.load(story, source_text, allow_stale=False)
        except StoryAnalysisCacheError as exc:
            self._error(str(exc))
            return None
        resolution = report.artifacts.get(AI_ENTITY_RESOLUTION_ARTIFACT)
        if not isinstance(resolution, EntityResolutionResult):
            self._error("Cached Story Analysis does not contain semantic entity resolution.")
            return None
        return resolution

    def _generate_planning_proposals(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        if self.semantic_interpretation_service is None:
            self._error("Semantic Story Interpretation service is not registered.")
            return
        if self.episode_scene_automation_service is None:
            self._error("Episode/Scene automation service is not registered.")
            return
        current = self._current_analysis(story)
        if current is None:
            return
        source_text, revision, baseline = current
        resolution = self._current_entity_resolution(story, source_text)
        if resolution is None:
            return

        try:
            semantic = self.semantic_interpretation_service.interpret(
                story_id=story.story_id,
                source_text=source_text,
                source_revision=revision,
                baseline=baseline,
                entity_resolution=resolution,
            )
            proposals = self.episode_scene_automation_service.generate(
                story_id=story.story_id,
                source_text=source_text,
                source_revision=revision,
                baseline=baseline,
                semantic=semantic,
            )
        except (AIProviderError, ValueError) as exc:
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

    def _generate_shot_proposals(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        if self.scene_shot_automation_service is None:
            self._error("Scene/Shot automation service is not registered.")
            return
        current = self._current_analysis(story)
        if current is None:
            return
        source_text, revision, baseline = current

        try:
            proposals = self.scene_shot_automation_service.generate(
                story_id=story.story_id,
                source_text=source_text,
                source_revision=revision,
                baseline=baseline,
            )
        except (AIProviderError, ValueError) as exc:
            self._error(str(exc))
            return

        scenes = len({item.payload.get("scene_id", "") for item in proposals})
        QMessageBox.information(
            self,
            "Shot Proposals Generated",
            f"Generated {len(proposals)} Shot proposal(s) across {scenes} Scene proposal(s).\n\n"
            "These are reviewable automation proposals only. No Shot Plan has been created, "
            "marked Ready, or approved in Production Planning.",
        )

    def _resolve_assets(self) -> None:
        """Resolve cached Story entities against canonical production truth without AI reruns."""
        story = self._selected_story()
        if story is None:
            return
        current = self._current_analysis(story)
        if current is None:
            return
        source_text, revision, _baseline = current
        resolution = self._current_entity_resolution(story, source_text)
        if resolution is None:
            return

        service = self.canonical_entity_asset_automation_service
        if service is None:
            service = CanonicalEntityAssetResolutionAutomationService(
                self.asset_browser.resolver,
                AutomationProposalService(self.stories.projects),
                AssetServiceStoryEntityCatalog(self.asset_browser.assets),
            )
            self.canonical_entity_asset_automation_service = service
        try:
            proposals = service.generate(
                story_id=story.story_id,
                source_revision=revision,
                entity_resolution=resolution,
            )
        except ValueError as exc:
            self._error(str(exc))
            return

        existing = sum(
            1
            for item in proposals
            if item.payload.get("resolution_kind") == "existing_canonical_asset"
        )
        ready = sum(1 for item in proposals if item.payload.get("canonical_status") == "resolved")
        review = len(proposals) - existing
        QMessageBox.information(
            self,
            "Canonical Entity & Asset Resolution",
            f"Resolved {len(proposals)} Story entity proposal(s).\n\n"
            f"Existing XPD matches: {existing}\n"
            f"Fully canonical-ready: {ready}\n"
            f"New/ambiguous entities requiring review: {review}\n\n"
            "No Asset, CAP, Master Reference, Ready state, or production approval was created.",
        )

    def _review_proposals(self) -> None:
        """Open a read-only proposal hierarchy without invoking any automation provider."""
        story = self._selected_story()
        if story is None:
            return
        current = self._current_analysis(story)
        if current is None:
            return
        _source_text, revision, _baseline = current
        proposal_service = AutomationProposalService(self.stories.projects)
        proposals = tuple(
            proposal
            for proposal in proposal_service.list_proposals()
            if proposal.provenance.source_story_id == story.story_id.strip().upper()
            and proposal.provenance.source_revision == revision
        )
        if not proposals:
            QMessageBox.information(
                self,
                "No Automation Proposals",
                "No automation proposals exist for the current Story revision.",
            )
            return
        dialog = AutomationProposalReviewDialog(
            proposal_service,
            story_id=story.story_id,
            source_revision=revision,
            parent=self,
        )
        dialog.exec()
