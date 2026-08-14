"""Episode/Scene proposal automation above the governed Phase 19.3 planners."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from vscs.domain.story_analysis import AnalysisResult

from .contracts import (
    AutomationProposal,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from .semantic_interpretation import SemanticStoryInterpretation
from .service import AutomationProposalService


@dataclass(frozen=True, slots=True)
class SceneProposalDraft:
    """Provider-neutral narrative scene proposal, never planning authority."""

    sequence_number: int
    title: str
    story_scope: str
    production_objective: str
    target_runtime_seconds: int
    setting_requirement: str
    required_events: tuple[str, ...]
    continuity_in: str = ""
    continuity_out: str = ""
    scene_constraints: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True, slots=True)
class EpisodeProposalDraft:
    """Provider-neutral narrative episode proposal, never planning authority."""

    sequence_number: int
    title: str
    story_scope: str
    production_objective: str
    target_runtime_seconds: int
    continuity_in: str = ""
    continuity_out: str = ""
    production_constraints: tuple[str, ...] = ()
    scenes: tuple[SceneProposalDraft, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True, slots=True)
class EpisodeSceneProposalDraft:
    """Complete provider response for one Story revision."""

    episodes: tuple[EpisodeProposalDraft, ...]
    diagnostics: tuple[str, ...] = ()


class EpisodeSceneProposalProvider(Protocol):
    """Semantic boundary for Story → Episode/Scene decomposition."""

    provider_name: str
    model_name: str

    def propose_episode_scenes(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
        semantic_payload: dict[str, object],
    ) -> EpisodeSceneProposalDraft:
        """Return reviewable Episode/Scene proposals only."""


class TemplateEpisodeSceneProposalProvider:
    """Deterministic offline decomposition for tests and development."""

    provider_name = "vscs-template"
    model_name = "deterministic"

    def propose_episode_scenes(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
        semantic_payload: dict[str, object],
    ) -> EpisodeSceneProposalDraft:
        del story_id
        summary = str(semantic_payload.get("summary", "")).strip()
        events = tuple(event.summary for event in baseline.ordered_timeline)
        if not events:
            events = (summary or source_text.strip()[:500],)
        scenes = tuple(
            SceneProposalDraft(
                sequence_number=index,
                title=f"Scene {index}",
                story_scope=event,
                production_objective=f"Present the story event: {event}",
                target_runtime_seconds=60,
                setting_requirement="Resolve from Story evidence during governed Scene review",
                required_events=(event,),
                continuity_in="Continue from the preceding story event" if index > 1 else "",
                continuity_out="Carry narrative state into the next story event",
                confidence=0.6,
            )
            for index, event in enumerate(events, start=1)
        )
        episode = EpisodeProposalDraft(
            sequence_number=1,
            title="Episode 1",
            story_scope=summary or source_text.strip()[:800],
            production_objective="Translate the supplied Story into governed production scenes.",
            target_runtime_seconds=max(60, sum(scene.target_runtime_seconds for scene in scenes)),
            scenes=scenes,
            confidence=0.6,
        )
        return EpisodeSceneProposalDraft(
            episodes=(episode,),
            diagnostics=("Deterministic Episode/Scene proposal provider used",),
        )


class EpisodeSceneProposalAutomationService:
    """Generate governed proposals without creating or approving planner authority."""

    def __init__(
        self,
        provider: EpisodeSceneProposalProvider,
        proposals: AutomationProposalService,
    ) -> None:
        self._provider = provider
        self._proposals = proposals

    def generate(
        self,
        *,
        story_id: str,
        source_text: str,
        source_revision: str,
        baseline: AnalysisResult,
        semantic: SemanticStoryInterpretation,
    ) -> tuple[AutomationProposal, ...]:
        normalized_story = story_id.strip().upper()
        revision = source_revision.strip()
        if not normalized_story or not revision or not source_text.strip():
            raise ValueError("Story ID, source revision and source text are required")
        if baseline.story_id.strip().upper() != normalized_story:
            raise ValueError("Episode/Scene baseline belongs to another Story")
        if baseline.source_revision and baseline.source_revision != revision:
            raise ValueError("Episode/Scene baseline is stale for this Story revision")
        if semantic.story_id != normalized_story or semantic.source_revision != revision:
            raise ValueError("Semantic interpretation is stale or belongs to another Story")
        if semantic.proposal.proposal_type is not AutomationProposalType.STORY_INTERPRETATION:
            raise ValueError("Episode/Scene automation requires a Story Interpretation proposal")

        draft = self._provider.propose_episode_scenes(
            story_id=normalized_story,
            source_text=source_text,
            baseline=baseline,
            semantic_payload=semantic.proposal.payload,
        )
        if not draft.episodes:
            raise ValueError("Episode/Scene provider returned no Episode proposals")

        generated: list[AutomationProposal] = []
        for episode in draft.episodes:
            episode_proposal = self._episode_proposal(
                normalized_story,
                revision,
                source_text,
                semantic,
                episode,
                draft.diagnostics,
            )
            generated.append(self._proposals.save(episode_proposal))
            for scene in episode.scenes:
                scene_proposal = self._scene_proposal(
                    normalized_story,
                    revision,
                    source_text,
                    semantic,
                    episode,
                    scene,
                    draft.diagnostics,
                )
                generated.append(self._proposals.save(scene_proposal))
        return tuple(generated)

    def _provenance(
        self,
        *,
        story_id: str,
        revision: str,
        confidence: float,
    ) -> AutomationProvenance:
        source_kind = (
            AutomationSourceKind.AI_INFERENCE
            if self._provider.provider_name != "vscs-template"
            else AutomationSourceKind.DETERMINISTIC_RESOLUTION
        )
        return AutomationProvenance(
            source_kind=source_kind,
            source_story_id=story_id,
            source_revision=revision,
            source_scope="complete Story revision plus Phase 19.5.2 semantic interpretation",
            provider=self._provider.provider_name,
            model=self._provider.model_name,
            confidence=max(0.0, min(1.0, confidence)),
            inference_note=(
                "Episode/Scene structure is proposed for human review. It does not create, "
                "mark Ready, or approve governed planning authority."
            ),
            resolution_method="semantic Story decomposition using existing Story Analysis context",
        )

    def _episode_proposal(
        self,
        story_id: str,
        revision: str,
        source_text: str,
        semantic: SemanticStoryInterpretation,
        episode: EpisodeProposalDraft,
        diagnostics: tuple[str, ...],
    ) -> AutomationProposal:
        target_id = f"EP-{episode.sequence_number:03d}"
        proposal_id = self._proposal_id(story_id, revision, "episode", target_id)
        return AutomationProposal(
            proposal_id=proposal_id,
            proposal_type=AutomationProposalType.EPISODE,
            target_id=target_id,
            payload={
                "story_id": story_id,
                "sequence_number": episode.sequence_number,
                "title": episode.title,
                "story_scope": episode.story_scope,
                "production_objective": episode.production_objective,
                "target_runtime_seconds": episode.target_runtime_seconds,
                "continuity_in": episode.continuity_in,
                "continuity_out": episode.continuity_out,
                "production_constraints": list(episode.production_constraints),
                "scene_count": len(episode.scenes),
                "diagnostics": list(diagnostics),
            },
            provenance=self._provenance(
                story_id=story_id,
                revision=revision,
                confidence=episode.confidence,
            ),
            metadata={
                "phase": "19.5.3",
                "semantic_proposal_id": semantic.proposal.proposal_id,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            },
        )

    def _scene_proposal(
        self,
        story_id: str,
        revision: str,
        source_text: str,
        semantic: SemanticStoryInterpretation,
        episode: EpisodeProposalDraft,
        scene: SceneProposalDraft,
        diagnostics: tuple[str, ...],
    ) -> AutomationProposal:
        episode_id = f"EP-{episode.sequence_number:03d}"
        target_id = f"{episode_id}-SC-{scene.sequence_number:03d}"
        proposal_id = self._proposal_id(story_id, revision, "scene", target_id)
        return AutomationProposal(
            proposal_id=proposal_id,
            proposal_type=AutomationProposalType.SCENE,
            target_id=target_id,
            payload={
                "episode_id": episode_id,
                "sequence_number": scene.sequence_number,
                "title": scene.title,
                "story_scope": scene.story_scope,
                "production_objective": scene.production_objective,
                "target_runtime_seconds": scene.target_runtime_seconds,
                "setting_requirement": scene.setting_requirement,
                "required_events": list(scene.required_events),
                "continuity_in": scene.continuity_in,
                "continuity_out": scene.continuity_out,
                "scene_constraints": list(scene.scene_constraints),
                "diagnostics": list(diagnostics),
            },
            provenance=self._provenance(
                story_id=story_id,
                revision=revision,
                confidence=scene.confidence,
            ),
            metadata={
                "phase": "19.5.3",
                "parent_episode_proposal_id": self._proposal_id(
                    story_id, revision, "episode", episode_id
                ),
                "semantic_proposal_id": semantic.proposal.proposal_id,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            },
        )

    @staticmethod
    def _proposal_id(story_id: str, revision: str, kind: str, target_id: str) -> str:
        digest = sha256(f"{story_id}|{revision}|{kind}|{target_id}".encode()).hexdigest()
        return f"AUT-{kind.upper()}-{digest[:12].upper()}"
