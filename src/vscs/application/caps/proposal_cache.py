"""Project-scoped, non-authoritative CAP proposal cache with atomic JSON writes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from vscs.application.caps.story_batch import StoryBatchProposal
from vscs.application.caps.story_specification import StoryCAPProposal


class CachedCAPProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    story_id: str
    story_fingerprint: str
    asset_id: str
    asset_fingerprint: str
    provider_fingerprint: str
    proposal: dict[str, object]


def cache_fingerprint(*parts: str) -> str:
    """Stable digest over ordered metadata, not Python's randomized hash."""
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()


class CAPProposalCache:
    """Only caches unapproved proposals; never changes CAP or approval records."""

    def __init__(self, project_directory: Path) -> None:
        self.directory = project_directory / "production" / "caps" / "proposal_cache"

    def _path(self, story_id: str, asset_id: str) -> Path:
        digest = cache_fingerprint(story_id, asset_id)
        return self.directory / f"{digest}.json"

    def load(
        self,
        story_id: str,
        asset_id: str,
        story_fingerprint: str,
        asset_fingerprint: str,
        provider_fingerprint: str,
    ) -> StoryBatchProposal | None:
        path = self._path(story_id, asset_id)
        if not path.is_file():
            return None
        try:
            record = CachedCAPProposal.model_validate_json(path.read_text(encoding="utf-8"))
            if (
                record.version != 1
                or record.story_id != story_id
                or record.asset_id != asset_id
                or record.story_fingerprint != story_fingerprint
                or record.asset_fingerprint != asset_fingerprint
                or record.provider_fingerprint != provider_fingerprint
            ):
                return None
            from vscs.application.caps.story_specification import StoryCAPProposal

            proposal = StoryCAPProposal.from_cache(record.proposal)
            if proposal.specification.asset_id != asset_id:
                return None
            return StoryBatchProposal(story_id, story_fingerprint, asset_id, proposal)
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def save(
        self, item: StoryBatchProposal, asset_fingerprint: str, provider_fingerprint: str
    ) -> None:
        record = CachedCAPProposal(
            version=1,
            story_id=item.story_id,
            story_fingerprint=item.story_fingerprint,
            asset_id=item.asset_id,
            asset_fingerprint=asset_fingerprint,
            provider_fingerprint=provider_fingerprint,
            proposal=item.proposal.to_cache(),
        )
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(item.story_id, item.asset_id)
        temporary = path.with_suffix(".tmp")
        try:
            temporary.write_text(record.model_dump_json(), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
