"""Human-governed canonical scope review for Phase 19.5.12.

Story analysis may detect many production elements. This service deliberately
separates prompt-local and Scene-continuity elements from persistent canonical
assets so the XPD does not become an inventory of incidental nouns.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import ClassVar

from vscs.application.assets import AssetNotFoundError, AssetService
from vscs.domain.assets import Asset, AssetCategory, AssetCreate, AssetStatus

from .contracts import AutomationProposal, AutomationProposalType
from .service import AutomationProposalService


class CanonicalScope(StrEnum):
    PROMPT_ELEMENT = "prompt_element"
    SCENE_CONTINUITY = "scene_continuity"
    PROJECT_CANONICAL = "project_canonical"
    STORY_UNIQUE_CANONICAL = "story_unique_canonical"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class CanonicalScopeRecommendation:
    scope: CanonicalScope
    reason: str


@dataclass(frozen=True, slots=True)
class SafeScopeReviewSummary:
    """Counts for one human-authorized bulk safe-scope operation."""

    prompt_elements: int
    scene_continuity: int
    skipped: int

    @property
    def eligible(self) -> int:
        return self.prompt_elements + self.scene_continuity


class CanonicalScopeReviewService:
    """Persist explicit human scope and XPD decisions without auto-approving assets."""

    _PERSISTENT_CATEGORIES: ClassVar[frozenset[str]] = frozenset(
        {"character", "ship", "vehicle", "planet", "uniform"}
    )
    _SAFE_BULK_SCOPES: ClassVar[frozenset[CanonicalScope]] = frozenset(
        {CanonicalScope.PROMPT_ELEMENT, CanonicalScope.SCENE_CONTINUITY}
    )
    _GENERIC_INCIDENTAL_NOUNS: ClassVar[frozenset[str]] = frozenset(
        {
            "road",
            "rock",
            "sandwich",
            "chair",
            "chairs",
            "cabinet",
            "cabinets",
            "rack",
            "racks",
            "case",
            "cases",
            "table",
            "tables",
            "cup",
            "cups",
            "glass",
            "glasses",
            "crate",
            "crates",
            "shelf",
            "shelves",
            "workstation",
            "workstations",
        }
    )
    _GENERIC_INCIDENTAL_MODIFIERS: ClassVar[frozenset[str]] = frozenset(
        {
            "storage",
            "equipment",
            "generic",
            "ordinary",
            "standard",
            "simple",
            "small",
            "large",
            "metal",
            "metallic",
            "nearby",
        }
    )
    _ANONYMOUS_CHARACTER_TERMS: ClassVar[frozenset[str]] = frozenset(
        {
            "unknown",
            "unidentified",
            "figure",
            "figures",
            "people",
            "person",
            "team",
            "group",
            "crew",
        }
    )
    _GENERIC_LOCATION_NOUNS: ClassVar[frozenset[str]] = frozenset(
        {"room", "corridor", "hall", "area", "bay", "platform", "surface"}
    )
    _GENERIC_LOCATION_MODIFIERS: ClassVar[frozenset[str]] = frozenset(
        {
            "operations",
            "operation",
            "control",
            "storage",
            "engineering",
            "briefing",
            "service",
            "maintenance",
            "main",
            "outer",
            "inner",
        }
    )

    def __init__(self, assets: AssetService, proposals: AutomationProposalService) -> None:
        self._assets = assets
        self._proposals = proposals

    def entity_proposal(
        self, story_id: str, source_revision: str, entity_name: str
    ) -> AutomationProposal:
        story = story_id.strip().upper()
        revision = source_revision.strip()
        matches = tuple(
            proposal
            for proposal in self._proposals.list_proposals()
            if proposal.proposal_type is AutomationProposalType.ASSET
            and proposal.provenance.source_story_id == story
            and proposal.provenance.source_revision == revision
            and str(proposal.payload.get("name", "")).casefold() == entity_name.strip().casefold()
        )
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one current asset proposal for {entity_name!r}; found {len(matches)}"
            )
        return matches[0]

    @staticmethod
    def is_resolved_canonical(proposal: AutomationProposal) -> bool:
        payload = proposal.payload
        return bool(
            payload.get("resolution_kind") == "existing_canonical_asset"
            and payload.get("matched_asset_id")
        )

    def recommend(self, proposal: AutomationProposal) -> CanonicalScopeRecommendation:
        payload = proposal.payload
        if self.is_resolved_canonical(proposal):
            return CanonicalScopeRecommendation(
                CanonicalScope.PROJECT_CANONICAL,
                "already resolves to an existing canonical XPD identity",
            )

        category = str(payload.get("expected_asset_category", "")).casefold()
        name = str(payload.get("name", "")).strip()
        tokens = self._tokens(name)

        if self._is_generic_incidental(tokens):
            return CanonicalScopeRecommendation(
                CanonicalScope.PROMPT_ELEMENT,
                "generic set dressing or incidental production detail does not require persistent identity",
            )

        if category == "character" and tokens & self._ANONYMOUS_CHARACTER_TERMS:
            return CanonicalScopeRecommendation(
                CanonicalScope.SCENE_CONTINUITY,
                "anonymous or group character presence should remain local unless human review identifies persistent canon",
            )

        if category in self._PERSISTENT_CATEGORIES:
            return CanonicalScopeRecommendation(
                CanonicalScope.STORY_UNIQUE_CANONICAL,
                "persistent identity category requires canonical review",
            )

        if category == "location":
            if self._is_generic_location(tokens):
                return CanonicalScopeRecommendation(
                    CanonicalScope.SCENE_CONTINUITY,
                    "generic location is local production context unless explicitly promoted to canon",
                )
            if self._looks_named(name):
                return CanonicalScopeRecommendation(
                    CanonicalScope.STORY_UNIQUE_CANONICAL,
                    "specific named location may require persistent Story identity",
                )

        return CanonicalScopeRecommendation(
            CanonicalScope.SCENE_CONTINUITY,
            "retain for local continuity unless a human promotes it to project canon",
        )

    def preview_safe_recommendations(
        self, *, story_id: str, source_revision: str
    ) -> SafeScopeReviewSummary:
        """Count recommendations safe for one explicit bulk human decision.

        Only unmatched/new entities with no prior scope decision are eligible.
        Possible XPD duplicates, existing matches and canonical candidates are
        deliberately excluded from this bulk operation.
        """
        eligible, total = self._safe_recommendations(story_id, source_revision)
        return SafeScopeReviewSummary(
            prompt_elements=sum(
                recommendation.scope is CanonicalScope.PROMPT_ELEMENT
                for _proposal, recommendation in eligible
            ),
            scene_continuity=sum(
                recommendation.scope is CanonicalScope.SCENE_CONTINUITY
                for _proposal, recommendation in eligible
            ),
            skipped=total - len(eligible),
        )

    def accept_safe_recommendations(
        self,
        *,
        story_id: str,
        source_revision: str,
        reviewed_by: str = "VSCS human reviewer",
    ) -> SafeScopeReviewSummary:
        """Persist only safe non-XPD scopes after explicit human confirmation."""
        eligible, total = self._safe_recommendations(story_id, source_revision)
        reviewer = reviewed_by.strip() or "VSCS human reviewer"
        prompt_elements = 0
        scene_continuity = 0
        for proposal, recommendation in eligible:
            payload = dict(proposal.payload)
            payload["canonical_scope"] = recommendation.scope.value
            payload["canonical_scope_reviewed_by"] = reviewer
            payload["canonical_scope_resolution_source"] = "human_bulk_safe_review"
            self._proposals.save(replace(proposal, payload=payload))
            if recommendation.scope is CanonicalScope.PROMPT_ELEMENT:
                prompt_elements += 1
            else:
                scene_continuity += 1
        return SafeScopeReviewSummary(
            prompt_elements=prompt_elements,
            scene_continuity=scene_continuity,
            skipped=total - len(eligible),
        )

    def set_scope(
        self,
        *,
        story_id: str,
        source_revision: str,
        entity_name: str,
        scope: CanonicalScope,
        reviewed_by: str = "VSCS human reviewer",
    ) -> AutomationProposal:
        proposal = self.entity_proposal(story_id, source_revision, entity_name)
        if self.is_resolved_canonical(proposal) and scope is not CanonicalScope.PROJECT_CANONICAL:
            raise ValueError(
                f"{entity_name!r} already has a canonical XPD identity. "
                "Use a future explicit Change Canonical Resolution workflow to alter it."
            )
        payload = dict(proposal.payload)
        payload["canonical_scope"] = scope.value
        payload["canonical_scope_reviewed_by"] = reviewed_by.strip() or "VSCS human reviewer"
        return self._proposals.save(replace(proposal, payload=payload))

    def accept_existing(
        self,
        *,
        story_id: str,
        source_revision: str,
        entity_name: str,
        asset_id: str,
        reviewed_by: str = "VSCS human reviewer",
    ) -> AutomationProposal:
        proposal = self.entity_proposal(story_id, source_revision, entity_name)
        asset = self._assets.get(asset_id)
        expected = str(proposal.payload.get("expected_asset_category", ""))
        if asset.category.value != expected:
            raise ValueError(
                f"Cannot bind {entity_name!r} ({expected}) to {asset.name!r} "
                f"({asset.category.value}); canonical categories differ"
            )
        payload = dict(proposal.payload)
        payload.update(
            {
                "resolution_kind": "existing_canonical_asset",
                "matched_asset_id": asset.asset_id,
                "matched_asset_name": asset.name,
                "canonical_scope": CanonicalScope.PROJECT_CANONICAL.value,
                "canonical_scope_reviewed_by": reviewed_by.strip() or "VSCS human reviewer",
                "canonical_resolution_source": "human_review",
            }
        )
        return self._proposals.save(replace(proposal, payload=payload))

    def reject_candidate(
        self,
        *,
        story_id: str,
        source_revision: str,
        entity_name: str,
        asset_id: str,
        reviewed_by: str = "VSCS human reviewer",
    ) -> AutomationProposal:
        proposal = self.entity_proposal(story_id, source_revision, entity_name)
        if self.is_resolved_canonical(proposal):
            raise ValueError(
                f"{entity_name!r} is already resolved canonically and cannot reject candidates."
            )
        payload = dict(proposal.payload)
        rejected = [str(item) for item in payload.get("rejected_canonical_asset_ids", [])]
        normalized = asset_id.strip().upper()
        if normalized and normalized not in rejected:
            rejected.append(normalized)
        payload["rejected_canonical_asset_ids"] = rejected
        payload["canonical_scope_reviewed_by"] = reviewed_by.strip() or "VSCS human reviewer"
        return self._proposals.save(replace(proposal, payload=payload))

    def create_story_canonical(
        self,
        *,
        story_id: str,
        source_revision: str,
        entity_name: str,
        reviewed_by: str = "VSCS human reviewer",
    ) -> Asset:
        proposal = self.entity_proposal(story_id, source_revision, entity_name)
        if self.is_resolved_canonical(proposal):
            raise ValueError(f"{entity_name!r} already has a canonical XPD identity")
        category = AssetCategory(str(proposal.payload.get("expected_asset_category", "other")))
        digest = (
            hashlib.sha256(
                f"{story_id.strip().upper()}|{source_revision}|{entity_name.casefold()}".encode()
            )
            .hexdigest()[:10]
            .upper()
        )
        prefix = category.value[:3].upper()
        asset_id = f"STORY-{prefix}-{digest}"
        try:
            asset = self._assets.get(asset_id)
        except AssetNotFoundError:
            asset = self._assets.create(
                AssetCreate(
                    asset_id=asset_id,
                    name=entity_name,
                    category=category,
                    description=(
                        f"Story-introduced canonical candidate from {story_id.strip().upper()}. "
                        "Requires CAP/Master Reference review before production approval."
                    ),
                    status=AssetStatus.DRAFT,
                    tags=("story-canonical-candidate", story_id.strip().upper()),
                )
            )
        self.accept_existing(
            story_id=story_id,
            source_revision=source_revision,
            entity_name=entity_name,
            asset_id=asset.asset_id,
            reviewed_by=reviewed_by,
        )
        proposal = self.entity_proposal(story_id, source_revision, entity_name)
        payload = dict(proposal.payload)
        payload["canonical_scope"] = CanonicalScope.STORY_UNIQUE_CANONICAL.value
        payload["canonical_resolution_source"] = "human_created_draft"
        self._proposals.save(replace(proposal, payload=payload))
        return asset

    def compatible_assets(
        self, *, story_id: str, source_revision: str, entity_name: str
    ) -> tuple[Asset, ...]:
        proposal = self.entity_proposal(story_id, source_revision, entity_name)
        category = str(proposal.payload.get("expected_asset_category", ""))
        rejected = {
            str(item).upper() for item in proposal.payload.get("rejected_canonical_asset_ids", [])
        }
        return tuple(
            asset
            for asset in self._assets.list()
            if asset.category.value == category and asset.asset_id not in rejected
        )

    def _safe_recommendations(
        self, story_id: str, source_revision: str
    ) -> tuple[
        tuple[tuple[AutomationProposal, CanonicalScopeRecommendation], ...],
        int,
    ]:
        story = story_id.strip().upper()
        revision = source_revision.strip()
        proposals = tuple(
            proposal
            for proposal in self._proposals.list_proposals()
            if proposal.proposal_type is AutomationProposalType.ASSET
            and proposal.provenance.source_story_id == story
            and proposal.provenance.source_revision == revision
        )
        eligible: list[tuple[AutomationProposal, CanonicalScopeRecommendation]] = []
        for proposal in proposals:
            payload = proposal.payload
            if self.is_resolved_canonical(proposal):
                continue
            if str(payload.get("canonical_scope", "")).strip():
                continue
            # Only true new/no-match entities are safe to bulk classify. A
            # possible duplicate or any entity carrying a candidate match must
            # remain an individual canonical decision.
            if str(payload.get("resolution_kind", "")) != "new":
                continue
            if str(payload.get("matched_asset_id", "")).strip():
                continue
            recommendation = self.recommend(proposal)
            if recommendation.scope not in self._SAFE_BULK_SCOPES:
                continue
            eligible.append((proposal, recommendation))
        return tuple(eligible), len(proposals)

    @classmethod
    def _is_generic_incidental(cls, tokens: frozenset[str]) -> bool:
        if not tokens or not tokens & cls._GENERIC_INCIDENTAL_NOUNS:
            return False
        allowed = cls._GENERIC_INCIDENTAL_NOUNS | cls._GENERIC_INCIDENTAL_MODIFIERS
        return tokens.issubset(allowed)

    @classmethod
    def _is_generic_location(cls, tokens: frozenset[str]) -> bool:
        if not tokens or not tokens & cls._GENERIC_LOCATION_NOUNS:
            return False
        allowed = cls._GENERIC_LOCATION_NOUNS | cls._GENERIC_LOCATION_MODIFIERS
        return tokens.issubset(allowed)

    @staticmethod
    def _tokens(value: str) -> frozenset[str]:
        normalized = "".join(ch if ch.isalnum() else " " for ch in value.casefold())
        return frozenset(normalized.split())

    @staticmethod
    def _looks_named(value: str) -> bool:
        words = value.split()
        return bool(words) and (any(char.isdigit() for char in value) or len(words) >= 2)
