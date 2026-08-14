"""Semantic Story Interpretation built on the existing Story Analysis authority."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from vscs.application.story_analysis.ai_analysis import EntityResolutionService
from vscs.domain.story_analysis import AnalysisResult, EntityResolutionResult

from .contracts import (
    AutomationProposal,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from .service import AutomationProposalService


@dataclass(frozen=True, slots=True)
class SemanticStoryInterpretation:
    """Structured, source-grounded interpretation before governed planning."""

    story_id: str
    source_revision: str
    entity_resolution: EntityResolutionResult
    proposal: AutomationProposal


class SemanticStoryInterpretationService:
    """Convert existing Story Intelligence into a governed automation proposal.

    Phase 19.5.2 intentionally reuses Phase 18 Story Analysis and deterministic
    entity resolution. It does not create Episode, Scene, Shot, Asset or other
    governed planning authority and cannot approve anything.
    """

    def __init__(
        self,
        entity_resolution: EntityResolutionService,
        proposals: AutomationProposalService,
    ) -> None:
        self._entity_resolution = entity_resolution
        self._proposals = proposals

    def interpret(
        self,
        *,
        story_id: str,
        source_text: str,
        source_revision: str,
        baseline: AnalysisResult,
        persist: bool = True,
    ) -> SemanticStoryInterpretation:
        normalized_story_id = story_id.strip().upper()
        normalized_revision = source_revision.strip()
        if not normalized_story_id:
            raise ValueError("Story ID is required for semantic interpretation")
        if not source_text.strip():
            raise ValueError("Story source text is required for semantic interpretation")
        if not normalized_revision:
            raise ValueError("Story source revision is required for semantic interpretation")
        if baseline.story_id.strip().upper() != normalized_story_id:
            raise ValueError("Semantic interpretation baseline belongs to another Story")
        if baseline.source_revision and baseline.source_revision != normalized_revision:
            raise ValueError("Semantic interpretation baseline is stale for this Story revision")

        resolution = self._entity_resolution.analyze(
            story_id=normalized_story_id,
            source_text=source_text,
            baseline=baseline,
        )
        proposal = self._proposal(
            story_id=normalized_story_id,
            source_revision=normalized_revision,
            source_text=source_text,
            resolution=resolution,
        )
        if persist:
            proposal = self._proposals.save(proposal)
        return SemanticStoryInterpretation(
            story_id=normalized_story_id,
            source_revision=normalized_revision,
            entity_resolution=resolution,
            proposal=proposal,
        )

    @staticmethod
    def _proposal(
        *,
        story_id: str,
        source_revision: str,
        source_text: str,
        resolution: EntityResolutionResult,
    ) -> AutomationProposal:
        digest = sha256(f"{story_id}|{source_revision}|semantic".encode()).hexdigest()[:12].upper()
        candidates = [
            {
                "candidate_id": item.candidate_id,
                "name": item.name,
                "category": item.category.value,
                "description": item.description,
                "aliases": list(item.aliases),
                "attributes": dict(item.attributes),
                "confidence": item.confidence,
                "match_kind": item.match_kind.value,
                "matched_asset_id": item.matched_asset_id,
                "matched_asset_name": item.matched_asset_name,
                "evidence": [span.model_dump(mode="json") for span in item.evidence],
            }
            for item in resolution.candidates
        ]
        metadata = resolution.metadata.model_dump(mode="json")
        provider_kind = (
            AutomationSourceKind.AI_INFERENCE
            if any("OpenAI" in diagnostic for diagnostic in resolution.diagnostics)
            else AutomationSourceKind.DETERMINISTIC_RESOLUTION
        )
        provider = "openai" if provider_kind is AutomationSourceKind.AI_INFERENCE else "vscs"
        model = "configured-story-analysis-model" if provider_kind is AutomationSourceKind.AI_INFERENCE else "deterministic"
        confidence_values = [item.confidence for item in resolution.candidates]
        confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else resolution.metadata.confidence
        )
        return AutomationProposal(
            proposal_id=f"AUT-SEMANTIC-{digest}",
            proposal_type=AutomationProposalType.STORY_INTERPRETATION,
            target_id=story_id,
            payload={
                "summary": metadata.get("summary", ""),
                "themes": metadata.get("themes", []),
                "tone": metadata.get("tone", []),
                "setting": metadata.get("setting", []),
                "production_notes": metadata.get("production_notes", []),
                "entities": candidates,
                "diagnostics": list(resolution.diagnostics),
            },
            provenance=AutomationProvenance(
                source_kind=provider_kind,
                source_story_id=story_id,
                source_revision=source_revision,
                source_scope="complete Story source supplied to Story Analysis",
                provider=provider,
                model=model,
                confidence=confidence,
                inference_note=(
                    "Semantic interpretation only; all production entities remain proposals "
                    "and canonical identity is resolved by VSCS."
                ),
                resolution_method="existing Story Analysis plus deterministic entity resolution",
            ),
            metadata={
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
                "phase": "19.5.2",
            },
        )
