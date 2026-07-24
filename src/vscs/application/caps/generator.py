"""Automated Canonical Asset Profile generation service."""

from __future__ import annotations

from vscs.application.assets import AssetService
from vscs.application.caps.service import CAPService
from vscs.domain.caps import CAPCreate, CAPStatus
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

    def generate_and_create(self, asset_id: str, story_context: str) -> CAPCreate:
        """Generate and persist a new CAP in Draft status."""
        draft = self.generate_draft(asset_id, story_context)
        notes = self._production_notes(draft)
        value = CAPCreate(
            asset_id=asset_id,
            title=draft.title,
            version="1.0",
            status=CAPStatus.DRAFT,
            canonical_description=draft.canonical_description,
            visual_identity=draft.visual_identity,
            production_notes=notes,
        )
        self.caps.create(value)
        return value

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
        if draft.unresolved_questions:
            sections.append(
                "Unresolved questions:\n"
                + "\n".join(f"- {item}" for item in draft.unresolved_questions)
            )
        if draft.source_summary:
            sections.append(f"Source summary:\n{draft.source_summary.strip()}")
        return "\n\n".join(section for section in sections if section)
