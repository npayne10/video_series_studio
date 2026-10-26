"""Phase 20.19.3B.5: governed, project-scoped Story-to-CAP batch proposals.

This is an advisory, read-only preview. No CAP/asset creation or provider video
submission; story metadata is never treated as evidence of unmentioned geometry.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from vscs.application.caps.service import CAPNotFoundError
from vscs.application.caps.story_specification import (
    StoryCAPProposal,
    StoryCAPSpecificationService,
)
from vscs.application.story.lifecycle import StoryLifecycleService, StoryStatus


class StoryBatchError(ValueError):
    """Refuse absent or unapproved project Story authority."""


@dataclass(frozen=True)
class StoryBatchProposal:
    """One proposed asset with its project Story provenance."""

    story_id: str
    story_fingerprint: str
    asset_id: str
    proposal: StoryCAPProposal


@dataclass(frozen=True)
class StoryBatchPreview:
    """Non-mutating selection results; incomplete items remain explicit."""

    story_id: str
    candidates: tuple[StoryBatchProposal, ...]
    skipped: tuple[str, ...]


class StoryCAPBatchService:
    """Collect proposals only from approved project Story and registered assets."""

    def __init__(
        self,
        stories: StoryLifecycleService,
        generator: StoryCAPSpecificationService,
    ) -> None:
        self.stories = stories
        self.generator = generator

    def preview(self, story_id: str, asset_ids: tuple[str, ...]) -> StoryBatchPreview:
        story = self.stories.story(story_id)
        if story is None or story.status not in {StoryStatus.APPROVED, StoryStatus.LOCKED}:
            raise StoryBatchError("Story must exist in this project and be Approved or Locked")
        context = story.description.strip()
        if not context:
            raise StoryBatchError(
                "Approved Story description is empty; no grounded prose is available"
            )
        fingerprint = hashlib.sha256(
            (story.story_id + "\n" + story.title + "\n" + context).encode("utf-8")
        ).hexdigest()
        candidates: list[StoryBatchProposal] = []
        skipped: list[str] = []
        seen: set[str] = set()
        for raw_id in asset_ids:
            asset_id = raw_id.strip().upper()
            if not asset_id or asset_id in seen:
                continue
            seen.add(asset_id)
            try:
                try:
                    existing = self.generator.specifications.get(asset_id)
                except CAPNotFoundError:
                    existing = None
                if existing is not None:
                    skipped.append(f"{asset_id}: existing specification requires revision review")
                    continue
                proposal = self.generator.propose(asset_id, context)
                candidates.append(
                    StoryBatchProposal(story.story_id, fingerprint, asset_id, proposal)
                )
            except (LookupError, RuntimeError, ValueError) as exc:
                skipped.append(f"{asset_id}: {exc}")
        return StoryBatchPreview(story.story_id, tuple(candidates), tuple(skipped))
