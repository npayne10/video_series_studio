"""Typed Story Workspace extension for governed Phase 19.5 planning proposals."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout

from vscs.application.automation import (
    ActionPerformanceProposalAutomationService,
    AutomationProposalService,
    CanonicalEntityAssetResolutionAutomationService,
    EnvironmentProposalAutomationService,
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
    semantic_interpretation_service: SemanticStoryInterpretationService | None = None
    episode_scene_automation_service: EpisodeSceneProposalAutomationService | None = None
    scene_shot_automation_service: SceneShotProposalAutomationService | None = None
    canonical_entity_asset_automation_service: (
        CanonicalEntityAssetResolutionAutomationService | None
    ) = None
    action_performance_automation_service: ActionPerformanceProposalAutomationService | None = None
    environment_automation_service: EnvironmentProposalAutomationService | None = None

    def _install_story_panel(self) -> None:
        super()._install_story_panel()
        panel = self.story_new_button.parentWidget()
        panel_layout = panel.layout() if panel is not None else None
        toolbar_item = panel_layout.itemAt(1) if isinstance(panel_layout, QVBoxLayout) else None
        toolbar = toolbar_item.layout() if toolbar_item is not None else None
        if not isinstance(toolbar, QHBoxLayout):
            raise RuntimeError("Story Workspace toolbar is unavailable.")
        actions = (
            ("Planning Proposals…", "generatePlanningProposals", self._generate_planning_proposals),
            ("Shot Proposals…", "generateShotProposals", self._generate_shot_proposals),
            ("Resolve Assets…", "resolveCanonicalAssets", self._resolve_assets),
            (
                "Performance Proposals…",
                "generatePerformanceProposals",
                self._generate_performance_proposals,
            ),
            (
                "Environment Proposals…",
                "generateEnvironmentProposals",
                self._generate_environment_proposals,
            ),
            ("Review Proposals…", "reviewAutomationProposals", self._review_proposals),
        )
        buttons: list[QPushButton] = []
        for offset, (label, name, callback) in enumerate(actions, start=4):
            button = QPushButton(label, panel)
            button.setObjectName(name)
            button.clicked.connect(callback)
            toolbar.insertWidget(offset, button)
            buttons.append(button)
        (
            self.planning_proposals_button,
            self.shot_proposals_button,
            self.resolve_assets_button,
            self.performance_proposals_button,
            self.environment_proposals_button,
            self.review_proposals_button,
        ) = buttons

    def _set_story_actions(self, story: StoryRecord | None) -> None:
        super()._set_story_actions(story)
        enabled = story is not None and not story.archived
        for button in (
            self.planning_proposals_button,
            self.shot_proposals_button,
            self.resolve_assets_button,
            self.performance_proposals_button,
            self.environment_proposals_button,
            self.review_proposals_button,
        ):
            button.setEnabled(enabled)

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
        self, story: StoryRecord, source_text: str
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
        if (
            story is None
            or self.semantic_interpretation_service is None
            or self.episode_scene_automation_service is None
        ):
            self._error("Planning automation services are not registered.")
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
        episodes = sum(item.proposal_type.value == "episode" for item in proposals)
        scenes = sum(item.proposal_type.value == "scene" for item in proposals)
        QMessageBox.information(
            self,
            "Planning Proposals Generated",
            f"Generated {episodes} Episode proposal(s) and {scenes} Scene proposal(s).\n\nNo governed planning authority was created.",
        )

    def _generate_shot_proposals(self) -> None:
        story = self._selected_story()
        if story is None or self.scene_shot_automation_service is None:
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
            f"Generated {len(proposals)} Shot proposal(s) across {scenes} Scene proposal(s).\n\nNo governed Shot Plan was created.",
        )

    def _resolve_assets(self) -> None:
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
                story_id=story.story_id, source_revision=revision, entity_resolution=resolution
            )
        except ValueError as exc:
            self._error(str(exc))
            return
        existing = sum(
            item.payload.get("resolution_kind") == "existing_canonical_asset" for item in proposals
        )
        ready = sum(item.payload.get("canonical_status") == "resolved" for item in proposals)
        QMessageBox.information(
            self,
            "Canonical Entity & Asset Resolution",
            f"Resolved {len(proposals)} Story entity proposal(s).\n\nExisting XPD matches: {existing}\nFully canonical-ready: {ready}\nNew/ambiguous entities requiring review: {len(proposals) - existing}\n\nNo canonical authority was created.",
        )

    def _generate_performance_proposals(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        if self.action_performance_automation_service is None:
            self._error("Action/Performance automation service is not registered.")
            return
        current = self._current_analysis(story)
        if current is None:
            return
        source_text, revision, _baseline = current
        try:
            proposals = self.action_performance_automation_service.generate(
                story_id=story.story_id, source_text=source_text, source_revision=revision
            )
        except (AIProviderError, ValueError) as exc:
            self._error(str(exc))
            return
        dialogue = sum(
            bool(str(item.payload.get("spoken_content", "")).strip()) for item in proposals
        )
        QMessageBox.information(
            self,
            "Action, Dialogue & Performance Proposals Generated",
            f"Generated {len(proposals)} performance proposal(s).\n"
            f"Proposals containing supported spoken content: {dialogue}.\n\n"
            "These are reviewable proposals only. No Phase 19.4.2 Action & Performance Draft "
            "was created, marked Ready, compiled, or approved.",
        )

    def _generate_environment_proposals(self) -> None:
        story = self._selected_story()
        if story is None:
            return
        if self.environment_automation_service is None:
            self._error("Environment automation service is not registered.")
            return
        current = self._current_analysis(story)
        if current is None:
            return
        source_text, revision, _baseline = current
        try:
            proposals = self.environment_automation_service.generate(
                story_id=story.story_id,
                source_text=source_text,
                source_revision=revision,
            )
        except (AIProviderError, ValueError) as exc:
            self._error(str(exc))
            return
        unknown_physics = sum(
            item.payload.get("gravity_m_s2") is None
            and item.payload.get("pressure_kpa") is None
            and item.payload.get("temperature_c") is None
            for item in proposals
        )
        QMessageBox.information(
            self,
            "Environment Production Proposals Generated",
            f"Generated {len(proposals)} Environment proposal(s).\n"
            f"Proposals preserving unspecified core physical values as unknown: {unknown_physics}.\n\n"
            "These are reviewable proposals only. No governed Environment Plan was created, "
            "marked Ready, or approved.",
        )

    def _review_proposals(self) -> None:
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
        AutomationProposalReviewDialog(
            proposal_service, story_id=story.story_id, source_revision=revision, parent=self
        ).exec()
