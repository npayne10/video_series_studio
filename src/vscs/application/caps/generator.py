"""Automated Canonical Asset Profile generation service."""

from __future__ import annotations

from vscs.application.assets import AssetService
from vscs.application.caps.service import CAPService
from vscs.application.caps.structured_knowledge import CAPStructuredKnowledgeService
from vscs.domain.caps import (
    CanonicalConstraintKind,
    CAPCreate,
    CAPStatus,
    KnowledgeAuthority,
    PersistedCanonicalConstraint,
    PersistedCanonicalFact,
    PersistedFunctionalCapability,
)
from vscs.domain.caps.generation import CAPGenerationRequest, GeneratedCAPDraft
from vscs.infrastructure.ai.provider import AIProviderError, CAPGenerationProvider
from vscs.infrastructure.logging import LoggingService


class CAPGenerationError(RuntimeError):
    """Raised when an automated CAP draft cannot be generated or stored."""


class CAPGeneratorService:
    """Generate moderated CAP drafts from registered assets and story context."""

    def __init__(
        self,
        assets: AssetService,
        caps: CAPService,
        provider: CAPGenerationProvider,
    ) -> None:
        self.assets = assets
        self.caps = caps
        self.provider = provider
        self.structured_knowledge = CAPStructuredKnowledgeService(caps, provider)
        self._logger = LoggingService.get_logger("caps.generator")

    def generate_draft(self, asset_id: str, story_context: str) -> GeneratedCAPDraft:
        """Generate a validated draft without changing project data."""
        if not story_context.strip():
            raise CAPGenerationError("Story context is required to generate a CAP")
        asset = self.assets.get(asset_id)
        request = CAPGenerationRequest(
            asset_id=asset.asset_id,
            asset_name=asset.name,
            asset_category=asset.category.value,
            asset_description=asset.description,
            story_context=story_context,
        )
        try:
            draft = self.provider.generate_cap(request)
        except AIProviderError as exc:
            raise CAPGenerationError(str(exc)) from exc
        self._logger.info("CAP draft generated for asset: %s", asset.asset_id)
        return draft

    def create_from_draft(self, asset_id: str, draft: GeneratedCAPDraft) -> CAPCreate:
        """Persist an explicitly approved generated draft as a Draft CAP."""
        notes = self._production_notes(draft)
        facts = tuple(
            PersistedCanonicalFact(
                key=f"fact_{index:03d}",
                value=fact.fact,
                source=fact.evidence,
                authority=KnowledgeAuthority.APPROVED,
                confidence=fact.confidence,
            )
            for index, fact in enumerate(draft.canonical_facts, start=1)
        )
        capabilities = tuple(
            PersistedFunctionalCapability(
                capability=capability,
                description="Approved CAP functional capability",
                source=draft.source_summary,
                authority=KnowledgeAuthority.APPROVED,
                confidence=draft.confidence.functional_capabilities,
            )
            for capability in draft.functional_capabilities
        )
        constraints = (
            *(
                PersistedCanonicalConstraint(
                    kind=CanonicalConstraintKind.REQUIRED,
                    rule=rule,
                    rationale="Approved CAP continuity rule",
                    source=draft.source_summary,
                    authority=KnowledgeAuthority.APPROVED,
                    confidence=draft.confidence.continuity_rules,
                )
                for rule in draft.continuity_rules
            ),
            *(
                PersistedCanonicalConstraint(
                    kind=CanonicalConstraintKind.FORBIDDEN,
                    rule=rule,
                    rationale="Approved prohibited variation",
                    source=draft.source_summary,
                    authority=KnowledgeAuthority.APPROVED,
                    confidence=draft.confidence.prohibited_variations,
                )
                for rule in draft.prohibited_variations
            ),
        )
        value = CAPCreate(
            asset_id=asset_id,
            title=draft.title,
            version="1.0",
            status=CAPStatus.DRAFT,
            canonical_description=draft.canonical_description,
            visual_identity=draft.visual_identity,
            production_notes=notes,
            facts=facts,
            functional_identity=capabilities,
            constraints=constraints,
            semantic_tags=draft.semantic_tags,
            production_classifications=draft.production_classifications,
            behaviour_references=draft.behaviour_references,
            production_metadata={
                "structured_source": "approved-cap-draft",
                **draft.production_metadata,
            },
        )
        self.caps.create(value)
        self._logger.info("Approved generated CAP draft stored for asset: %s", asset_id)
        return value

    def generate_and_create(self, asset_id: str, story_context: str) -> CAPCreate:
        """Generate and persist a new CAP in Draft status.

        This compatibility method bypasses moderation. Presentation workflows should
        call ``generate_draft`` and then ``create_from_draft`` after explicit approval.
        """
        draft = self.generate_draft(asset_id, story_context)
        return self.create_from_draft(asset_id, draft)

    @staticmethod
    def _production_notes(draft: GeneratedCAPDraft) -> str:
        sections = [draft.production_notes.strip()]
        if draft.continuity_rules:
            sections.append(
                "Continuity rules:\n" + "\n".join(f"- {item}" for item in draft.continuity_rules)
            )
        if draft.prohibited_variations:
            sections.append(
                "Prohibited variations:\n"
                + "\n".join(f"- {item}" for item in draft.prohibited_variations)
            )
        if draft.functional_capabilities:
            sections.append(
                "Functional capabilities:\n"
                + "\n".join(f"- {item}" for item in draft.functional_capabilities)
            )
        if draft.unresolved_questions:
            sections.append(
                "Unresolved questions:\n"
                + "\n".join(f"- {item}" for item in draft.unresolved_questions)
            )
        if draft.contradictions:
            sections.append(
                "Source contradictions:\n" + "\n".join(f"- {item}" for item in draft.contradictions)
            )
        if draft.canonical_facts:
            fact_lines = []
            for fact in draft.canonical_facts:
                fact_lines.append(
                    f"- [{fact.confidence:.0%}] {fact.fact}\n  Evidence: {fact.evidence}"
                )
            sections.append("Extracted canonical facts:\n" + "\n".join(fact_lines))
        confidence = draft.confidence
        sections.append(
            "AI confidence scores:\n"
            f"- Canonical description: {confidence.canonical_description:.0%}\n"
            f"- Visual identity: {confidence.visual_identity:.0%}\n"
            f"- Production notes: {confidence.production_notes:.0%}\n"
            f"- Continuity rules: {confidence.continuity_rules:.0%}\n"
            f"- Prohibited variations: {confidence.prohibited_variations:.0%}\n"
            f"- Functional capabilities: {confidence.functional_capabilities:.0%}\n"
            f"- Overall: {confidence.overall:.0%}"
        )
        if draft.source_summary:
            sections.append(f"Source summary:\n{draft.source_summary.strip()}")
        return "\n\n".join(section for section in sections if section)
