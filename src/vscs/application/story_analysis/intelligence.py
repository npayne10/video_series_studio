"""Persistence and canonical promotion for approved Story Intelligence."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from vscs.application.assets import AssetService
from vscs.domain.assets import AssetCategory, AssetCreate, AssetStatus
from vscs.domain.story_analysis import (
    ApprovedStoryIntelligence,
    CandidateReviewStatus,
    EntityCandidate,
    EntityResolutionCategory,
    EntityResolutionResult,
    ResolutionMatchKind,
    StoryEntityDecision,
)


class StoryIntelligenceError(RuntimeError):
    """Raised when approved Story Intelligence cannot be persisted."""


class ApprovedStoryIntelligenceStore:
    """Persist one approved Story Intelligence document per project story."""

    DIRECTORY = "story_intelligence"

    def __init__(self, assets: AssetService) -> None:
        self.assets = assets

    def load(self, story_id: str) -> ApprovedStoryIntelligence:
        path = self._path(story_id)
        if not path.is_file():
            return ApprovedStoryIntelligence(story_id=story_id)
        try:
            return ApprovedStoryIntelligence.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise StoryIntelligenceError(
                f"Unable to read approved Story Intelligence for {story_id}: {exc}"
            ) from exc

    def save(self, intelligence: ApprovedStoryIntelligence) -> None:
        path = self._path(intelligence.story_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(
                json.dumps(intelligence.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StoryIntelligenceError(
                f"Unable to persist approved Story Intelligence for {intelligence.story_id}: {exc}"
            ) from exc

    def _path(self, story_id: str) -> Path:
        project = self.assets.projects.project_directory
        if project is None:
            raise StoryIntelligenceError("Open a VSCS project before persisting Story Intelligence")
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", story_id).strip("._") or "story"
        return project / ".vscs" / self.DIRECTORY / f"{safe_id}.json"


class ApprovedStoryIntelligenceService:
    """Restore review decisions and promote approved entities to canonical assets."""

    _CATEGORY_MAP: ClassVar[dict[EntityResolutionCategory, AssetCategory]] = {
        EntityResolutionCategory.CHARACTER: AssetCategory.CHARACTER,
        EntityResolutionCategory.SHIP: AssetCategory.SHIP,
        EntityResolutionCategory.PLANET: AssetCategory.PLANET,
        EntityResolutionCategory.LOCATION: AssetCategory.LOCATION,
        EntityResolutionCategory.VEHICLE: AssetCategory.VEHICLE,
        EntityResolutionCategory.PROP: AssetCategory.PROP,
        EntityResolutionCategory.TECHNOLOGY: AssetCategory.TECHNOLOGY,
        EntityResolutionCategory.ENVIRONMENT: AssetCategory.ENVIRONMENT,
    }
    _PREFIX_MAP: ClassVar[dict[EntityResolutionCategory, str]] = {
        EntityResolutionCategory.CHARACTER: "CHR",
        EntityResolutionCategory.SHIP: "SHP",
        EntityResolutionCategory.PLANET: "PLN",
        EntityResolutionCategory.LOCATION: "LOC",
        EntityResolutionCategory.VEHICLE: "VEH",
        EntityResolutionCategory.PROP: "PRP",
        EntityResolutionCategory.TECHNOLOGY: "TEC",
        EntityResolutionCategory.ENVIRONMENT: "ENV",
        EntityResolutionCategory.ORGANIZATION: "ORG",
        EntityResolutionCategory.SPECIES: "SPC",
        EntityResolutionCategory.OTHER: "AST",
    }

    def __init__(
        self,
        assets: AssetService,
        store: ApprovedStoryIntelligenceStore | None = None,
    ) -> None:
        self.assets = assets
        self.store = store or ApprovedStoryIntelligenceStore(assets)

    def restore(self, resolution: EntityResolutionResult) -> EntityResolutionResult:
        """Overlay persisted human decisions onto a fresh AI resolution result."""
        intelligence = self.store.load(resolution.story_id)
        candidates = []
        for candidate in resolution.candidates:
            decision = intelligence.decision(candidate.candidate_id)
            if decision is None:
                candidates.append(candidate)
                continue
            changes: dict[str, object] = {"review_status": decision.review_status}
            if (
                decision.review_status is CandidateReviewStatus.APPROVED
                and decision.canonical_asset_id
            ):
                changes.update(
                    {
                        "match_kind": ResolutionMatchKind.EXISTING,
                        "matched_asset_id": decision.canonical_asset_id,
                        "matched_asset_name": decision.canonical_asset_name or decision.name,
                    }
                )
            candidates.append(candidate.model_copy(update=changes))
        return resolution.model_copy(update={"candidates": tuple(candidates)})

    def save_metadata(self, resolution: EntityResolutionResult) -> ApprovedStoryIntelligence:
        """Persist automatically extracted narrative metadata without changing review decisions."""
        current = self.store.load(resolution.story_id)
        updated = current.model_copy(
            update={
                "source_revision": resolution.source_revision,
                "narrative_metadata": resolution.metadata,
                "updated_at": datetime.now(UTC),
            }
        )
        self.store.save(updated)
        return updated

    def approve(
        self,
        resolution: EntityResolutionResult,
        candidate: EntityCandidate,
    ) -> EntityCandidate:
        """Persist approval and ensure the entity has a canonical Asset registry identity."""
        canonical_id = candidate.matched_asset_id
        canonical_name = candidate.matched_asset_name or candidate.name
        if canonical_id is None:
            canonical_id = self._next_asset_id(candidate.category)
            created = self.assets.create(
                AssetCreate(
                    asset_id=canonical_id,
                    name=candidate.name,
                    category=self._asset_category(candidate.category),
                    description=candidate.description,
                    status=AssetStatus.DRAFT,
                    tags=(
                        "story-intelligence:approved-identity",
                        f"story:{resolution.story_id}",
                        f"ai-category:{candidate.category.value}",
                    ),
                )
            )
            canonical_id = created.asset_id
            canonical_name = created.name
        updated = candidate.model_copy(
            update={
                "review_status": CandidateReviewStatus.APPROVED,
                "match_kind": ResolutionMatchKind.EXISTING,
                "matched_asset_id": canonical_id,
                "matched_asset_name": canonical_name,
            }
        )
        self._save_decision(resolution, updated)
        return updated

    def reject(
        self,
        resolution: EntityResolutionResult,
        candidate: EntityCandidate,
    ) -> EntityCandidate:
        updated = candidate.model_copy(update={"review_status": CandidateReviewStatus.REJECTED})
        self._save_decision(resolution, updated)
        return updated

    def reset(
        self,
        resolution: EntityResolutionResult,
        candidate: EntityCandidate,
    ) -> EntityCandidate:
        updated = candidate.model_copy(update={"review_status": CandidateReviewStatus.PROPOSED})
        self._save_decision(resolution, updated)
        return updated

    def load(self, story_id: str) -> ApprovedStoryIntelligence:
        return self.store.load(story_id)

    def _save_decision(
        self,
        resolution: EntityResolutionResult,
        candidate: EntityCandidate,
    ) -> None:
        current = self.store.load(resolution.story_id)
        keep_canonical_link = candidate.review_status is CandidateReviewStatus.APPROVED
        decision = StoryEntityDecision(
            candidate_id=candidate.candidate_id,
            name=candidate.name,
            category=candidate.category,
            review_status=candidate.review_status,
            canonical_asset_id=candidate.matched_asset_id if keep_canonical_link else None,
            canonical_asset_name=candidate.matched_asset_name if keep_canonical_link else None,
            description=candidate.description,
            aliases=candidate.aliases,
            attributes=candidate.attributes,
            evidence=candidate.evidence,
            confidence=candidate.confidence,
            source_revision=resolution.source_revision,
        )
        decisions = tuple(
            decision if item.candidate_id == decision.candidate_id else item
            for item in current.decisions
        )
        if current.decision(decision.candidate_id) is None:
            decisions = (*decisions, decision)
        updated = current.model_copy(
            update={
                "source_revision": resolution.source_revision,
                "narrative_metadata": resolution.metadata,
                "decisions": decisions,
                "updated_at": datetime.now(UTC),
            }
        )
        self.store.save(updated)

    def _next_asset_id(self, category: EntityResolutionCategory) -> str:
        prefix = self._PREFIX_MAP.get(category, "AST")
        expression = re.compile(rf"^CAP-{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
        numbers = []
        for asset in self.assets.list():
            match = expression.match(asset.asset_id)
            if match:
                numbers.append(int(match.group(1)))
        return f"CAP-{prefix}-{max(numbers, default=0) + 1:03d}"

    @classmethod
    def _asset_category(cls, category: EntityResolutionCategory) -> AssetCategory:
        return cls._CATEGORY_MAP.get(category, AssetCategory.OTHER)
