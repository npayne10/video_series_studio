"""Provider-neutral AI contracts and CAP generation implementations."""

from __future__ import annotations

from typing import Protocol

from vscs.domain.caps.generation import (
    CAPCanonAnalysis,
    CAPGenerationRequest,
    CAPSectionConfidence,
    CanonicalFactExtraction,
    ExtractedCanonicalFact,
    GeneratedCAPDraft,
)


class AIProviderError(RuntimeError):
    """Raised when an AI provider cannot complete a generation request."""


class CAPGenerationProvider(Protocol):
    """Generate a structured CAP draft from story-grounded asset context."""

    def generate_cap(self, request: CAPGenerationRequest) -> GeneratedCAPDraft:
        """Return a validated CAP draft."""


class TemplateCAPGenerationProvider:
    """Deterministic local provider used for development and offline operation."""

    def generate_cap(self, request: CAPGenerationRequest) -> GeneratedCAPDraft:
        extraction = self._extract_facts(request)
        analysis = self._analyse_canon(request, extraction)
        return self._build_draft(request, analysis)

    @staticmethod
    def _extract_facts(request: CAPGenerationRequest) -> CanonicalFactExtraction:
        facts: list[ExtractedCanonicalFact] = []
        if request.asset_description:
            facts.append(
                ExtractedCanonicalFact(
                    fact=request.asset_description,
                    evidence="Existing approved asset description",
                    confidence=0.95,
                )
            )
        facts.append(
            ExtractedCanonicalFact(
                fact=request.story_context.strip(),
                evidence=request.story_context.strip()[:500],
                confidence=0.8,
            )
        )
        return CanonicalFactExtraction(
            facts=tuple(facts),
            candidate_claims=(
                "Visible details not explicitly stated in the supplied material require approval.",
            ),
        )

    @staticmethod
    def _analyse_canon(
        request: CAPGenerationRequest,
        extraction: CanonicalFactExtraction,
    ) -> CAPCanonAnalysis:
        return CAPCanonAnalysis(
            canonical_facts=extraction.facts,
            uncertainties=extraction.candidate_claims,
            source_summary=request.story_context.strip()[:1000],
        )

    @staticmethod
    def _build_draft(
        request: CAPGenerationRequest,
        analysis: CAPCanonAnalysis,
    ) -> GeneratedCAPDraft:
        description = "\n\n".join(fact.fact for fact in analysis.canonical_facts)
        return GeneratedCAPDraft(
            title=request.asset_name,
            canonical_description=description,
            visual_identity=(
                "Use only visible characteristics explicitly supported by the canonical facts "
                "and approved reference imagery."
            ),
            production_notes=(
                "Generated through the local multi-stage CAP intelligence pipeline. "
                "Review all sections before changing the CAP status from Draft."
            ),
            continuity_rules=(
                "Preserve every extracted canonical fact across generated appearances.",
                "Use approved reference images as the visual source of truth once available.",
            ),
            prohibited_variations=(
                "Do not introduce unsupported design changes as established canon.",
            ),
            unresolved_questions=analysis.uncertainties,
            source_summary=analysis.source_summary,
            canonical_facts=analysis.canonical_facts,
            contradictions=analysis.contradictions,
            confidence=CAPSectionConfidence(
                canonical_description=0.8,
                visual_identity=0.55,
                production_notes=0.75,
                continuity_rules=0.8,
                prohibited_variations=0.75,
                overall=0.73,
            ),
        )
