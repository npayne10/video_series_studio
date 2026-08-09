"""Application services for structured CAP knowledge proposal, review, and persistence."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from vscs.application.caps.service import CAPService
from vscs.domain.caps import (
    CanonicalConstraintKind,
    CAPUpdate,
    KnowledgeAuthority,
    PersistedCanonicalConstraint,
    PersistedCanonicalFact,
    PersistedFunctionalCapability,
    StructuredCAPKnowledge,
)
from vscs.domain.caps.generation import CAPGenerationRequest
from vscs.infrastructure.ai.provider import AIProviderError, CAPGenerationProvider


class StructuredKnowledgeProposal(BaseModel):
    """Human-reviewable proposal; never canonical until explicitly applied."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    knowledge: StructuredCAPKnowledge
    source_summary: str = ""
    unresolved_questions: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()


class StructuredKnowledgeError(RuntimeError):
    """Raised when structured CAP knowledge cannot be proposed or persisted."""


class CAPStructuredKnowledgeService:
    """Modernize legacy CAP prose into reviewed structured production knowledge."""

    def __init__(self, caps: CAPService, provider: CAPGenerationProvider) -> None:
        self.caps = caps
        self.provider = provider

    def propose(self, asset_id: str) -> StructuredKnowledgeProposal:
        """Use the configured CAP intelligence provider to propose structured knowledge.

        The proposal is intentionally non-mutating. AI-derived items remain PROPOSED
        until an operator explicitly calls ``apply`` after review.
        """
        cap = self.caps.get(asset_id)
        asset = self.caps.assets.get(asset_id)
        context = "\n\n".join(
            part
            for part in (
                cap.canonical_description.strip(),
                cap.visual_identity.strip(),
                cap.production_notes.strip(),
            )
            if part
        )
        request = CAPGenerationRequest(
            asset_id=asset.asset_id,
            asset_name=asset.name,
            asset_category=asset.category.value,
            asset_description=asset.description,
            story_context=context or cap.canonical_description,
        )
        try:
            draft = self.provider.generate_cap(request)
        except AIProviderError as exc:
            raise StructuredKnowledgeError(str(exc)) from exc

        facts = tuple(
            PersistedCanonicalFact(
                key=f"fact_{index:03d}",
                value=fact.fact,
                source=fact.evidence,
                authority=KnowledgeAuthority.PROPOSED,
                confidence=fact.confidence,
            )
            for index, fact in enumerate(draft.canonical_facts, start=1)
        )
        capabilities = tuple(
            PersistedFunctionalCapability(
                capability=capability,
                description="AI-proposed functional capability",
                source=draft.source_summary,
                authority=KnowledgeAuthority.PROPOSED,
                confidence=draft.confidence.functional_capabilities,
            )
            for capability in draft.functional_capabilities
        )
        constraints = tuple(
            PersistedCanonicalConstraint(
                kind=CanonicalConstraintKind.REQUIRED,
                rule=rule,
                rationale="AI-proposed continuity rule",
                source=draft.source_summary,
                authority=KnowledgeAuthority.PROPOSED,
                confidence=draft.confidence.continuity_rules,
            )
            for rule in draft.continuity_rules
        ) + tuple(
            PersistedCanonicalConstraint(
                kind=CanonicalConstraintKind.FORBIDDEN,
                rule=rule,
                rationale="AI-proposed prohibited variation",
                source=draft.source_summary,
                authority=KnowledgeAuthority.PROPOSED,
                confidence=draft.confidence.prohibited_variations,
            )
            for rule in draft.prohibited_variations
        )
        knowledge = StructuredCAPKnowledge(
            facts=facts,
            functional_identity=capabilities,
            constraints=constraints,
            semantic_tags=tuple(dict.fromkeys((*asset.tags, *draft.semantic_tags))),
            production_classifications=(
                tuple(draft.production_classifications) or (asset.category.value,)
            ),
            behaviour_references=draft.behaviour_references,
            production_metadata={
                "migration_source": "phase-19.1-ai-proposal",
                "provider": type(self.provider).__name__,
                **draft.production_metadata,
            },
        )
        return StructuredKnowledgeProposal(
            asset_id=asset.asset_id,
            knowledge=knowledge,
            source_summary=draft.source_summary,
            unresolved_questions=draft.unresolved_questions,
            contradictions=draft.contradictions,
        )

    def apply(
        self,
        asset_id: str,
        knowledge: StructuredCAPKnowledge,
        *,
        approve_proposed: bool = True,
    ) -> StructuredCAPKnowledge:
        """Persist explicitly reviewed structured knowledge for one CAP."""
        if not approve_proposed:
            raise StructuredKnowledgeError(
                "Structured knowledge must be explicitly approved before persistence"
            )
        approved = StructuredCAPKnowledge(
            schema_version=knowledge.schema_version,
            facts=tuple(
                item.model_copy(update={"authority": KnowledgeAuthority.APPROVED})
                for item in knowledge.facts
            ),
            functional_identity=tuple(
                item.model_copy(update={"authority": KnowledgeAuthority.APPROVED})
                for item in knowledge.functional_identity
            ),
            constraints=tuple(
                item.model_copy(update={"authority": KnowledgeAuthority.APPROVED})
                for item in knowledge.constraints
            ),
            semantic_tags=knowledge.semantic_tags,
            production_classifications=knowledge.production_classifications,
            behaviour_references=knowledge.behaviour_references,
            production_metadata=knowledge.production_metadata,
        )
        self.caps.update(
            asset_id,
            CAPUpdate(
                structured_schema_version=approved.schema_version,
                facts=approved.facts,
                functional_identity=approved.functional_identity,
                constraints=approved.constraints,
                semantic_tags=approved.semantic_tags,
                production_classifications=approved.production_classifications,
                behaviour_references=approved.behaviour_references,
                production_metadata=approved.production_metadata,
            ),
        )
        return approved

    def knowledge(self, asset_id: str) -> StructuredCAPKnowledge:
        """Return the currently persisted structured CAP knowledge."""
        cap = self.caps.get(asset_id)
        return StructuredCAPKnowledge(
            schema_version=cap.structured_schema_version,
            facts=cap.facts,
            functional_identity=cap.functional_identity,
            constraints=cap.constraints,
            semantic_tags=cap.semantic_tags,
            production_classifications=cap.production_classifications,
            behaviour_references=cap.behaviour_references,
            production_metadata=cap.production_metadata,
        )

    def needs_migration(self, asset_id: str) -> bool:
        """Return whether a CAP still lacks all structured production knowledge."""
        knowledge = self.knowledge(asset_id)
        return not any(
            (
                knowledge.facts,
                knowledge.functional_identity,
                knowledge.constraints,
                knowledge.semantic_tags,
                knowledge.production_classifications,
                knowledge.behaviour_references,
                knowledge.production_metadata,
            )
        )
