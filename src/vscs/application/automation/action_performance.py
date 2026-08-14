"""Action, Dialogue & Performance proposal automation for Phase 19.5.6."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from .contracts import (
    AutomationProposal,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from .service import AutomationProposalService


@dataclass(frozen=True, slots=True)
class ActionPerformanceProposalDraft:
    """Provider-neutral temporal/performance proposal for one proposed Shot."""

    temporal_narrative: str
    spoken_content: str = ""
    performance_direction: str = ""
    opening_state: str = ""
    closing_state: str = ""
    timing_notes: str = ""
    confidence: float = 0.5


class ActionPerformanceProposalProvider(Protocol):
    provider_name: str
    model_name: str

    def propose_action_performance(
        self,
        *,
        story_id: str,
        source_text: str,
        shot_payload: dict[str, object],
    ) -> ActionPerformanceProposalDraft: ...


class TemplateActionPerformanceProposalProvider:
    """Deterministic provider that never expands beyond existing Shot intent."""

    provider_name = "vscs-template"
    model_name = "deterministic"

    def propose_action_performance(
        self,
        *,
        story_id: str,
        source_text: str,
        shot_payload: dict[str, object],
    ) -> ActionPerformanceProposalDraft:
        del story_id, source_text
        runtime = shot_payload.get("target_runtime_seconds", "")
        return ActionPerformanceProposalDraft(
            temporal_narrative=str(shot_payload.get("required_action", "")).strip(),
            spoken_content=str(shot_payload.get("dialogue_requirement", "")).strip(),
            opening_state=str(shot_payload.get("continuity_in", "")).strip(),
            closing_state=str(shot_payload.get("continuity_out", "")).strip(),
            timing_notes=f"Target runtime: {runtime} seconds" if runtime else "",
            confidence=0.6,
        )


class ActionPerformanceProposalAutomationService:
    """Generate reviewable performance proposals without mutating Phase 19.4.2 authority."""

    def __init__(
        self,
        provider: ActionPerformanceProposalProvider,
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
    ) -> tuple[AutomationProposal, ...]:
        normalized_story = story_id.strip().upper()
        revision = source_revision.strip()
        if not normalized_story or not revision or not source_text.strip():
            raise ValueError("Story ID, source revision and source text are required")
        shots = tuple(
            item
            for item in self._proposals.list_proposals()
            if item.proposal_type is AutomationProposalType.SHOT
            and item.provenance.source_story_id == normalized_story
            and item.provenance.source_revision == revision
        )
        if not shots:
            raise ValueError("Generate current Shot proposals before performance proposals")

        generated: list[AutomationProposal] = []
        for shot in sorted(shots, key=lambda item: item.target_id):
            draft = self._provider.propose_action_performance(
                story_id=normalized_story,
                source_text=source_text,
                shot_payload=shot.payload,
            )
            if not draft.temporal_narrative.strip():
                raise ValueError(f"Performance proposal for {shot.target_id} has no temporal narrative")
            generated.append(
                self._proposals.save(
                    self._proposal(
                        story_id=normalized_story,
                        revision=revision,
                        source_text=source_text,
                        shot=shot,
                        draft=draft,
                    )
                )
            )
        return tuple(generated)

    def _proposal(
        self,
        *,
        story_id: str,
        revision: str,
        source_text: str,
        shot: AutomationProposal,
        draft: ActionPerformanceProposalDraft,
    ) -> AutomationProposal:
        digest = sha256(
            f"{story_id}|{revision}|action-performance|{shot.proposal_id}|{shot.target_id}".encode()
        ).hexdigest()
        source_kind = (
            AutomationSourceKind.AI_INFERENCE
            if self._provider.provider_name != "vscs-template"
            else AutomationSourceKind.DETERMINISTIC_RESOLUTION
        )
        return AutomationProposal(
            proposal_id=f"AUT-ACTION-PERFORMANCE-{digest[:12].upper()}",
            proposal_type=AutomationProposalType.ACTION_PERFORMANCE,
            target_id=shot.target_id,
            payload={
                "shot_id": shot.target_id,
                "temporal_narrative": draft.temporal_narrative,
                "spoken_content": draft.spoken_content,
                "performance_direction": draft.performance_direction,
                "opening_state": draft.opening_state,
                "closing_state": draft.closing_state,
                "timing_notes": draft.timing_notes,
            },
            provenance=AutomationProvenance(
                source_kind=source_kind,
                source_story_id=story_id,
                source_revision=revision,
                source_scope="current Phase 19.5.4 Shot proposal plus Story source",
                provider=self._provider.provider_name,
                model=self._provider.model_name,
                confidence=max(0.0, min(1.0, draft.confidence)),
                inference_note=(
                    "Action, dialogue and performance are proposed for human review only. "
                    "They do not create or mark Ready Phase 19.4.2 Action & Performance authority."
                ),
                resolution_method="semantic temporal and performance interpretation",
            ),
            metadata={
                "phase": "19.5.6",
                "parent_shot_proposal_id": shot.proposal_id,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            },
        )
