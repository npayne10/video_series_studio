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
from vscs.application.story.lifecycle import StoryLifecycleService, StoryRecord, StoryStatus


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

    def current_story_fingerprint(self, story_id: str) -> str:
        """Revalidate persisted Story authority without invoking an AI provider."""
        story = self.stories.story(story_id)
        if story is None or story.status not in {StoryStatus.APPROVED, StoryStatus.LOCKED}:
            raise StoryBatchError("Story must exist in this project and be Approved or Locked")
        context = story.description.strip()
        if not context:
            raise StoryBatchError(
                "Approved Story description is empty; no grounded prose is available"
            )
        source = self._source_text(story)
        identity = story.story_id + "\n" + story.title + "\n" + context
        if source:
            source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
            identity += (
                "\n"
                + str(getattr(story, "source_type", ""))
                + "\n"
                + str(getattr(story, "source_path", ""))
                + "\n"
                + source_hash
            )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _source_text(story: StoryRecord) -> str:
        """Read the current source with the same parser used by Story Analysis."""
        if not str(getattr(story, "source_path", "")).strip():
            return ""
        from vscs.application.story_analysis.source_reader import (
            StorySourceReader,
            StorySourceReadError,
        )

        try:
            return StorySourceReader().read(story)
        except StorySourceReadError as exc:
            raise StoryBatchError(f"Approved Story source cannot be read: {exc}") from exc

    def approved_source_text(self, story_id: str) -> str:
        """Return approved Story source or fail closed on a configured unreadable file."""
        story = self.stories.story(story_id)
        if story is None or story.status not in {StoryStatus.APPROVED, StoryStatus.LOCKED}:
            raise StoryBatchError("Story must exist in this project and be Approved or Locked")
        return self._source_text(story)

    def approved_story_context(self, story_id: str) -> str:
        """Provide detailed approved Story context without any unverified Shot claims."""
        self.current_story_fingerprint(story_id)
        story = self.stories.story(story_id)
        if story is None:
            raise StoryBatchError("Approved Story disappeared before CAP context preparation")
        description = story.description.strip()
        source = self._source_text(story)
        if not source:
            return description
        return (
            "APPROVED STORY DESCRIPTION:\n"
            + description
            + "\n\nAPPROVED STORY SOURCE TEXT:\n"
            + source
        )

    def preview(self, story_id: str, asset_ids: tuple[str, ...]) -> StoryBatchPreview:
        fingerprint = self.current_story_fingerprint(story_id)
        story = self.stories.story(story_id)
        if story is None:
            raise StoryBatchError("Story disappeared during preview")
        context = self.approved_story_context(story_id)
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
