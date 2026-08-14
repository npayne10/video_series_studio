"""Scene → Shot proposal automation above governed Shot Planning authority."""

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
from .service import AutomationProposalService


@dataclass(frozen=True, slots=True)
class ShotProposalDraft:
    """Provider-neutral narrative Shot proposal, never governed Shot authority."""

    sequence_number: int
    title: str
    narrative_purpose: str
    production_objective: str
    target_runtime_seconds: int
    required_action: str
    dialogue_requirement: str = ""
    continuity_in: str = ""
    continuity_out: str = ""
    shot_constraints: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True, slots=True)
class SceneShotProposalDraft:
    """Complete provider response for one proposed Scene."""

    shots: tuple[ShotProposalDraft, ...]
    diagnostics: tuple[str, ...] = ()


class SceneShotProposalProvider(Protocol):
    """Semantic boundary for Scene proposal → Shot proposal decomposition."""

    provider_name: str
    model_name: str

    def propose_scene_shots(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
        scene_payload: dict[str, object],
    ) -> SceneShotProposalDraft:
        """Return reviewable Shot proposals only."""


class TemplateSceneShotProposalProvider:
    """Deterministic offline Scene decomposition for tests and development."""

    provider_name = "vscs-template"
    model_name = "deterministic"

    def propose_scene_shots(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
        scene_payload: dict[str, object],
    ) -> SceneShotProposalDraft:
        del story_id, source_text, baseline
        scene_runtime = max(1, int(scene_payload.get("target_runtime_seconds", 60)))
        raw_events = scene_payload.get("required_events", [])
        events = tuple(str(value).strip() for value in raw_events if str(value).strip())
        if not events:
            fallback = str(scene_payload.get("story_scope", "")).strip() or "Present the Scene intent"
            events = (fallback,)

        count = len(events)
        base_runtime = max(1, scene_runtime // count)
        remaining = scene_runtime
        shots: list[ShotProposalDraft] = []
        for index, event in enumerate(events, start=1):
            runtime = remaining if index == count else min(base_runtime, remaining - (count - index))
            remaining -= runtime
            shots.append(
                ShotProposalDraft(
                    sequence_number=index,
                    title=f"Shot {index}",
                    narrative_purpose=event,
                    production_objective=f"Present the required Scene event: {event}",
                    target_runtime_seconds=max(1, runtime),
                    required_action=event,
                    continuity_in=(
                        "Continue from the preceding Shot state" if index > 1 else str(scene_payload.get("continuity_in", ""))
                    ),
                    continuity_out=(
                        str(scene_payload.get("continuity_out", ""))
                        if index == count
                        else "Carry visual and narrative state into the next Shot"
                    ),
                    shot_constraints=tuple(
                        str(value) for value in scene_payload.get("scene_constraints", []) if str(value).strip()
                    ),
                    confidence=0.6,
                )
            )
        return SceneShotProposalDraft(
            shots=tuple(shots),
            diagnostics=("Deterministic Scene/Shot proposal provider used",),
        )


class SceneShotProposalAutomationService:
    """Generate Shot proposals from current Scene proposals without creating Shot Plans."""

    def __init__(
        self,
        provider: SceneShotProposalProvider,
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
    ) -> tuple[AutomationProposal, ...]:
        normalized_story = story_id.strip().upper()
        revision = source_revision.strip()
        if not normalized_story or not revision or not source_text.strip():
            raise ValueError("Story ID, source revision and source text are required")
        if baseline.story_id.strip().upper() != normalized_story:
            raise ValueError("Scene/Shot baseline belongs to another Story")
        if baseline.source_revision and baseline.source_revision != revision:
            raise ValueError("Scene/Shot baseline is stale for this Story revision")

        scene_proposals = tuple(
            proposal
            for proposal in self._proposals.list_proposals()
            if proposal.proposal_type is AutomationProposalType.SCENE
            and proposal.provenance.source_story_id == normalized_story
            and proposal.provenance.source_revision == revision
        )
        if not scene_proposals:
            raise ValueError("Generate current Episode/Scene proposals before generating Shot proposals")

        generated: list[AutomationProposal] = []
        for scene in sorted(scene_proposals, key=lambda item: item.target_id):
            draft = self._provider.propose_scene_shots(
                story_id=normalized_story,
                source_text=source_text,
                baseline=baseline,
                scene_payload=scene.payload,
            )
            if not draft.shots:
                raise ValueError(f"Scene/Shot provider returned no Shots for {scene.target_id}")
            self._validate_runtime_budget(scene, draft)
            for shot in draft.shots:
                generated.append(
                    self._proposals.save(
                        self._shot_proposal(
                            story_id=normalized_story,
                            revision=revision,
                            source_text=source_text,
                            scene=scene,
                            shot=shot,
                            diagnostics=draft.diagnostics,
                        )
                    )
                )
        return tuple(generated)

    def _shot_proposal(
        self,
        *,
        story_id: str,
        revision: str,
        source_text: str,
        scene: AutomationProposal,
        shot: ShotProposalDraft,
        diagnostics: tuple[str, ...],
    ) -> AutomationProposal:
        target_id = f"{scene.target_id}-SHT-{shot.sequence_number:03d}"
        proposal_id = self._proposal_id(story_id, revision, scene.target_id, target_id)
        return AutomationProposal(
            proposal_id=proposal_id,
            proposal_type=AutomationProposalType.SHOT,
            target_id=target_id,
            payload={
                "scene_id": scene.target_id,
                "sequence_number": shot.sequence_number,
                "title": shot.title,
                "narrative_purpose": shot.narrative_purpose,
                "production_objective": shot.production_objective,
                "target_runtime_seconds": shot.target_runtime_seconds,
                "required_action": shot.required_action,
                "dialogue_requirement": shot.dialogue_requirement,
                "continuity_in": shot.continuity_in,
                "continuity_out": shot.continuity_out,
                "shot_constraints": list(shot.shot_constraints),
                "diagnostics": list(diagnostics),
            },
            provenance=self._provenance(
                story_id=story_id,
                revision=revision,
                confidence=shot.confidence,
            ),
            metadata={
                "phase": "19.5.4",
                "parent_scene_proposal_id": scene.proposal_id,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            },
        )

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
            source_scope="current Phase 19.5.3 Scene proposal plus Story Analysis context",
            provider=self._provider.provider_name,
            model=self._provider.model_name,
            confidence=max(0.0, min(1.0, confidence)),
            inference_note=(
                "Shot structure is proposed for human review. It does not create, mark Ready, "
                "or approve governed Shot Planning authority."
            ),
            resolution_method="semantic Scene decomposition using existing Story Analysis context",
        )

    @staticmethod
    def _validate_runtime_budget(
        scene: AutomationProposal,
        draft: SceneShotProposalDraft,
    ) -> None:
        scene_runtime = int(scene.payload.get("target_runtime_seconds", 0))
        if scene_runtime <= 0:
            raise ValueError(f"Scene proposal {scene.target_id} has no valid runtime budget")
        total = sum(shot.target_runtime_seconds for shot in draft.shots)
        if total > scene_runtime:
            raise ValueError(
                f"Shot proposals for {scene.target_id} exceed the Scene runtime budget "
                f"({total}s proposed for {scene_runtime}s)"
            )
        sequence = tuple(shot.sequence_number for shot in draft.shots)
        if sequence != tuple(range(1, len(draft.shots) + 1)):
            raise ValueError(f"Shot proposals for {scene.target_id} must use contiguous sequence numbers")

    @staticmethod
    def _proposal_id(story_id: str, revision: str, scene_id: str, target_id: str) -> str:
        digest = sha256(f"{story_id}|{revision}|shot|{scene_id}|{target_id}".encode()).hexdigest()
        return f"AUT-SHOT-{digest[:12].upper()}"
