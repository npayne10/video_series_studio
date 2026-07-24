"""Provider-neutral AI contracts and CAP generation implementations."""

from __future__ import annotations

from typing import Protocol

from vscs.domain.caps.generation import CAPGenerationRequest, GeneratedCAPDraft


class AIProviderError(RuntimeError):
    """Raised when an AI provider cannot complete a generation request."""


class CAPGenerationProvider(Protocol):
    """Generate a structured CAP draft from story-grounded asset context."""

    def generate_cap(self, request: CAPGenerationRequest) -> GeneratedCAPDraft:
        """Return a validated CAP draft."""


class TemplateCAPGenerationProvider:
    """Deterministic local provider used for development and offline operation."""

    def generate_cap(self, request: CAPGenerationRequest) -> GeneratedCAPDraft:
        description = request.asset_description or (
            f"{request.asset_name} is a {request.asset_category} identified in the supplied story."
        )
        canonical_description = (
            f"{description}\n\nStory-grounded context:\n{request.story_context.strip()}"
        )
        return GeneratedCAPDraft(
            title=request.asset_name,
            canonical_description=canonical_description,
            visual_identity=(
                "Derive visible characteristics only from approved story facts "
                "and reference imagery. Any inferred detail must remain "
                "provisional until user approval."
            ),
            production_notes=(
                "Generated locally by the VSCS template provider. "
                "Review all inferred details before changing the CAP "
                "status from Draft."
            ),
            continuity_rules=(
                "Preserve all explicit story facts across every generated appearance.",
                "Use approved reference images as the visual source of truth once available.",
            ),
            prohibited_variations=(
                "Do not introduce unsupported design changes as established canon.",
            ),
            unresolved_questions=(
                "Which visual details are explicit canon and which require creative approval?",
            ),
            source_summary=request.story_context.strip()[:1000],
        )
