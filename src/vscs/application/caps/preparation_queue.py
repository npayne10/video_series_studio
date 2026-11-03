"""Offline cache-first planning for the existing Story to CAP batch review."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.caps.proposal_cache import (
    CAPProposalCache,
    provider_cache_fingerprint,
)
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService


@dataclass(frozen=True)
class CAPQueueItem:
    asset_id: str
    name: str
    category: str
    status: str
    context_authority: str
    context_fingerprint: str
    note: str


@dataclass(frozen=True)
class CAPPreparationPlan:
    story_id: str
    story_fingerprint: str
    provider_label: str
    items: tuple[CAPQueueItem, ...]


class CAPPreparationQueueService:
    """Plan a batch without generating, caching, or persisting anything."""

    def __init__(
        self,
        review: StoryCAPBatchReviewService,
        cache: CAPProposalCache | None,
        provider: object,
    ) -> None:
        self.review = review
        self.cache = cache
        self.provider = provider

    def plan(self, story_id: str) -> CAPPreparationPlan:
        fingerprint = self.review.batch.current_story_fingerprint(story_id)
        provider_fingerprint = provider_cache_fingerprint(self.provider)
        provider_label = (
            f"{type(self.provider).__name__} "
            f"({getattr(self.provider, '_model', 'model unspecified')})"
        )
        items: list[CAPQueueItem] = []
        for candidate in self.review.discover(story_id):
            if candidate.has_specification:
                items.append(
                    CAPQueueItem(
                        candidate.asset_id,
                        candidate.name,
                        candidate.category,
                        "already_specified",
                        "not_inspected",
                        "",
                        "Existing specification; use the governed revision workflow.",
                    )
                )
                continue
            try:
                manifest = self.review.prepare_context(story_id, candidate.asset_id)
            except (OSError, RuntimeError, ValueError) as exc:
                items.append(
                    CAPQueueItem(
                        candidate.asset_id,
                        candidate.name,
                        candidate.category,
                        "context_blocked",
                        "unavailable",
                        "",
                        f"Context cannot be prepared: {exc}",
                    )
                )
                continue
            authority = (
                "verified_ready_shot"
                if any(source.authority == "verified_ready_shot" for source in manifest.sources)
                else "unverified_shot"
                if any(source.authority == "unverified_shot" for source in manifest.sources)
                else "approved_story_context"
            )
            cache_status = (
                self.cache.inspect(
                    story_id,
                    candidate.asset_id,
                    fingerprint,
                    manifest.asset_fingerprint,
                    provider_fingerprint,
                    manifest.fingerprint,
                ).status
                if self.cache is not None
                else "missing"
            )
            note = {
                "cached_current": "Current cached proposal, still unapproved; review offline.",
                "legacy_cached": (
                    "Legacy cached proposal: Story/asset/provider match, but "
                    "governed Shot context was not fingerprinted when generated."
                ),
                "stale": "Stale cache: changed Story, asset, provider or context.",
                "invalid": "Invalid cache record; cannot reuse automatically.",
                "missing": (
                    "No cached proposal. New provider generation requires explicit consent."
                ),
            }[cache_status]
            if candidate.has_cap:
                note = "Existing Draft CAP without specification. " + note
            items.append(
                CAPQueueItem(
                    candidate.asset_id,
                    candidate.name,
                    candidate.category,
                    cache_status,
                    authority,
                    manifest.fingerprint,
                    note,
                )
            )
        if fingerprint != self.review.batch.current_story_fingerprint(story_id):
            raise ValueError("Approved Story changed during queue preparation")
        return CAPPreparationPlan(story_id, fingerprint, provider_label, tuple(items))
