"""Unit coverage for Phase 18.2.7 approved Story Intelligence persistence."""

from __future__ import annotations

from pathlib import Path

from vscs.application.story_analysis import ApprovedStoryIntelligenceService
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.domain.story_analysis import (
    AIEntityDraft,
    AINarrativeMetadata,
    CandidateReviewStatus,
    EntityCandidate,
    EntityResolutionCategory,
    EntityResolutionResult,
    ResolutionMatchKind,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Assets:
    def __init__(self, root: Path, initial: tuple[Asset, ...] = ()) -> None:
        self.projects = _Projects(root)
        self._items = {asset.asset_id: asset for asset in initial}
        self._next_id = len(self._items) + 1

    def list(self, **_kwargs) -> tuple[Asset, ...]:
        return tuple(self._items.values())

    def create(self, value):
        asset = Asset(
            id=self._next_id,
            asset_id=value.asset_id,
            name=value.name,
            category=value.category,
            description=value.description,
            status=value.status,
            file_path=value.file_path,
            tags=value.tags,
        )
        self._next_id += 1
        self._items[asset.asset_id] = asset
        return asset


def _candidate(
    *,
    name: str,
    category: EntityResolutionCategory,
    matched_asset_id: str | None = None,
) -> EntityCandidate:
    return EntityCandidate(
        candidate_id=f"candidate:{category.value}:{name.casefold().replace(' ', '-')}",
        name=name,
        category=category,
        description=f"Canonical {category.value}",
        confidence=0.95,
        match_kind=(
            ResolutionMatchKind.EXISTING if matched_asset_id else ResolutionMatchKind.NEW
        ),
        matched_asset_id=matched_asset_id,
        matched_asset_name=name if matched_asset_id else None,
    )


def _resolution(*candidates: EntityCandidate) -> EntityResolutionResult:
    return EntityResolutionResult(
        story_id="xorix-trailer",
        source_revision="rev-1",
        candidates=candidates,
        metadata=AINarrativeMetadata(
            summary="Arrival at Xorix",
            themes=("discovery",),
            confidence=0.9,
        ),
    )


def test_existing_xpd_approval_persists_and_restores_canonical_link(tmp_path: Path) -> None:
    existing = Asset(
        id=1,
        asset_id="CAP-SHP-001",
        name="Iron Horizon",
        category=AssetCategory.SHIP,
        description="Survey vessel",
        status=AssetStatus.APPROVED,
        file_path=None,
        tags=(),
    )
    service = ApprovedStoryIntelligenceService(_Assets(tmp_path, (existing,)))
    candidate = _candidate(
        name="Iron Horizon",
        category=EntityResolutionCategory.SHIP,
        matched_asset_id="CAP-SHP-001",
    )
    resolution = _resolution(candidate)

    approved = service.approve(resolution, candidate)
    restored = service.restore(_resolution(candidate))

    assert approved.review_status is CandidateReviewStatus.APPROVED
    assert restored.candidates[0].review_status is CandidateReviewStatus.APPROVED
    assert restored.candidates[0].matched_asset_id == "CAP-SHP-001"
    intelligence = service.load("xorix-trailer")
    assert intelligence.narrative_metadata.summary == "Arrival at Xorix"
    assert intelligence.decisions[0].canonical_asset_id == "CAP-SHP-001"


def test_approved_new_entity_creates_one_draft_canonical_asset(tmp_path: Path) -> None:
    assets = _Assets(tmp_path)
    service = ApprovedStoryIntelligenceService(assets)
    candidate = _candidate(
        name="Ambassador Andruish",
        category=EntityResolutionCategory.CHARACTER,
    )
    resolution = _resolution(candidate)

    approved = service.approve(resolution, candidate)

    assert approved.review_status is CandidateReviewStatus.APPROVED
    assert approved.matched_asset_id == "CAP-CHR-001"
    created = assets.list()
    assert len(created) == 1
    assert created[0].name == "Ambassador Andruish"
    assert created[0].status is AssetStatus.DRAFT
    assert "story-intelligence:approved-identity" in created[0].tags


def test_rejected_candidate_and_ai_metadata_survive_reload(tmp_path: Path) -> None:
    service = ApprovedStoryIntelligenceService(_Assets(tmp_path))
    candidate = _candidate(name="Unknown Relic", category=EntityResolutionCategory.PROP)
    resolution = _resolution(candidate)

    service.save_metadata(resolution)
    rejected = service.reject(resolution, candidate)
    restored = service.restore(_resolution(candidate))

    assert rejected.review_status is CandidateReviewStatus.REJECTED
    assert restored.candidates[0].review_status is CandidateReviewStatus.REJECTED
    intelligence = service.load("xorix-trailer")
    assert intelligence.narrative_metadata.themes == ("discovery",)
