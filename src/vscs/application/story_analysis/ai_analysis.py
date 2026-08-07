"""AI story enrichment and production-entity resolution."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Protocol

from vscs.application.assets import AssetService
from vscs.domain.assets import Asset, AssetCategory
from vscs.domain.story_analysis import (
    AIStoryAnalysisDraft,
    AnalysisResult,
    EntityCandidate,
    EntityResolutionCategory,
    EntityResolutionResult,
    ResolutionMatchKind,
    SourceSpan,
)


class StoryAIAnalysisProvider(Protocol):
    """Produce structured narrative enrichment from source-grounded story data."""

    def analyze_story(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
    ) -> AIStoryAnalysisDraft:
        """Return source-grounded AI entity and narrative proposals."""


@dataclass(frozen=True, slots=True)
class ExistingAssetReference:
    asset_id: str
    name: str
    category: AssetCategory


class StoryEntityCatalog(Protocol):
    def assets(self) -> tuple[ExistingAssetReference, ...]:
        """Return canonical production assets eligible for entity matching."""


class EmptyStoryEntityCatalog:
    def assets(self) -> tuple[ExistingAssetReference, ...]:
        return ()


class AssetServiceStoryEntityCatalog:
    """Expose project XPD assets through the entity-resolution catalog contract."""

    def __init__(self, assets: AssetService) -> None:
        self._assets = assets

    def assets(self) -> tuple[ExistingAssetReference, ...]:
        try:
            items = self._assets.list()
        except Exception:
            return ()
        return tuple(self._reference(asset) for asset in items)

    @staticmethod
    def _reference(asset: Asset) -> ExistingAssetReference:
        return ExistingAssetReference(
            asset_id=asset.asset_id,
            name=asset.name,
            category=asset.category,
        )


class EntityResolutionService:
    """Resolve AI entity proposals against the current production asset catalog."""

    def __init__(
        self,
        provider: StoryAIAnalysisProvider,
        catalog: StoryEntityCatalog | None = None,
    ) -> None:
        self._provider = provider
        self._catalog = catalog or EmptyStoryEntityCatalog()

    def analyze(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
    ) -> EntityResolutionResult:
        draft = self._provider.analyze_story(
            story_id=story_id,
            source_text=source_text,
            baseline=baseline,
        )
        assets = self._catalog.assets()
        candidates = tuple(
            self._resolve_candidate(story_id, source_text, proposal, assets)
            for proposal in draft.entities
        )
        diagnostics = (
            *draft.diagnostics,
            f"AI proposed {len(candidates)} production entities",
            f"Matched {sum(1 for item in candidates if item.matched_asset_id)} existing assets",
        )
        return EntityResolutionResult(
            story_id=story_id,
            source_revision=baseline.source_revision,
            candidates=candidates,
            metadata=draft.metadata,
            diagnostics=diagnostics,
        )

    def _resolve_candidate(self, story_id, source_text, proposal, assets):
        match_kind, asset = self._match(proposal.name, proposal.aliases, proposal.category, assets)
        evidence = tuple(
            span
            for text in proposal.evidence_text
            if (span := self._locate_evidence(story_id, source_text, text)) is not None
        )
        return EntityCandidate(
            candidate_id=self._candidate_id(proposal.category, proposal.name),
            name=proposal.name,
            category=proposal.category,
            description=proposal.description,
            aliases=proposal.aliases,
            evidence=evidence,
            attributes=proposal.attributes,
            confidence=proposal.confidence,
            match_kind=match_kind,
            matched_asset_id=asset.asset_id if asset else None,
            matched_asset_name=asset.name if asset else None,
        )

    @classmethod
    def _match(cls, name, aliases, category, assets):
        names = {name.casefold(), *(alias.casefold() for alias in aliases)}
        compatible = [asset for asset in assets if cls._compatible(category, asset.category)]
        exact = [asset for asset in compatible if asset.name.casefold() in names]
        if len(exact) == 1:
            return ResolutionMatchKind.EXISTING, exact[0]
        if len(exact) > 1:
            return ResolutionMatchKind.POSSIBLE_DUPLICATE, exact[0]
        normalized = cls._normalize(name)
        fuzzy = [asset for asset in compatible if cls._normalize(asset.name) == normalized]
        if fuzzy:
            return ResolutionMatchKind.POSSIBLE_DUPLICATE, fuzzy[0]
        return ResolutionMatchKind.NEW, None

    @staticmethod
    def _compatible(category: EntityResolutionCategory, asset_category: AssetCategory) -> bool:
        mapping = {
            EntityResolutionCategory.CHARACTER: AssetCategory.CHARACTER,
            EntityResolutionCategory.SHIP: AssetCategory.SHIP,
            EntityResolutionCategory.PLANET: AssetCategory.PLANET,
            EntityResolutionCategory.LOCATION: AssetCategory.LOCATION,
            EntityResolutionCategory.VEHICLE: AssetCategory.VEHICLE,
            EntityResolutionCategory.PROP: AssetCategory.PROP,
            EntityResolutionCategory.TECHNOLOGY: AssetCategory.TECHNOLOGY,
            EntityResolutionCategory.ENVIRONMENT: AssetCategory.ENVIRONMENT,
        }
        expected = mapping.get(category)
        return expected is None or asset_category is expected

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    @staticmethod
    def _candidate_id(category: EntityResolutionCategory, name: str) -> str:
        digest = sha1(name.casefold().encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
        slug = "-".join(name.casefold().split())[:48]
        return f"candidate:{category.value}:{slug}:{digest}"

    @staticmethod
    def _locate_evidence(story_id: str, source_text: str, evidence: str) -> SourceSpan | None:
        needle = evidence.strip()
        if not needle:
            return None
        start = source_text.casefold().find(needle.casefold())
        if start < 0:
            return None
        end = start + len(needle)
        return SourceSpan(
            story_id=story_id,
            start_offset=start,
            end_offset=end,
            start_line=source_text.count("\n", 0, start) + 1,
            end_line=source_text.count("\n", 0, end) + 1,
            excerpt=source_text[start:end],
        )
