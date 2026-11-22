"""Immutable, non-authoritative CAP decision records when no field is accepted.

These records deliberately live outside CAP specification/asset repositories.
They preserve a human refusal or deferral without creating an empty CAP, an
approved reference, or any production authority.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vscs.application.caps.context_preparation import CAPContextManifest, CAPContextSource
from vscs.application.caps.design_completion import (
    DesignReviewPackage,
    reviewed_canonical_attributes,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification

# Issue #54 added optional Story/Shot provenance to each design field. Historical
# Issue #57 review-only records were sealed before those keys existed. Preserve
# their original hash calculation; never rewrite their immutable JSON files.
_POST_V1_FIELD_PROVENANCE = frozenset(
    {
        "source_record_id",
        "source_field",
        "source_fingerprint",
        "source_excerpt",
        "shot_authority",
        "shot_source_record_id",
        "shot_source_fingerprint",
        "shot_excerpt",
    }
)


def _review_digest(
    story_id: str,
    asset_id: str,
    story_fingerprint: str,
    context_fingerprint: str,
    asset_fingerprint: str,
    base_fingerprint: str,
    review: DesignReviewPackage,
    *,
    pre_story_provenance: bool = False,
) -> str:
    review_payload = review.model_dump(mode="json")
    if pre_story_provenance:
        for field in review_payload["fields"]:
            for key in _POST_V1_FIELD_PROVENANCE:
                field.pop(key)
    identity = {
        "story_id": story_id,
        "asset_id": asset_id,
        "story_fingerprint": story_fingerprint,
        "context_fingerprint": context_fingerprint,
        "asset_fingerprint": asset_fingerprint,
        "base_fingerprint": base_fingerprint,
        "review": review_payload,
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _stored_review_digest(data: dict[str, object]) -> str:
    """Seal the review as stored, before Pydantic supplies newer optional defaults."""
    identity = {
        key: data[key]
        for key in (
            "story_id",
            "asset_id",
            "story_fingerprint",
            "context_fingerprint",
            "asset_fingerprint",
            "base_fingerprint",
            "review",
        )
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class UnresolvedCAPReviewRecord(BaseModel):
    """One human-reviewed unresolved proposal, not a materialized specification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    record_id: str = Field(min_length=1)
    outcome: Literal["no_eligible_attributes"] = "no_eligible_attributes"
    story_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    story_fingerprint: str = Field(min_length=1)
    context_fingerprint: str = Field(min_length=1)
    asset_fingerprint: str = Field(min_length=1)
    base_fingerprint: str = Field(min_length=1)
    reviewed_at_utc: str = Field(min_length=1)
    specification_snapshot: CAPStructuredSpecification
    review: DesignReviewPackage
    context_sources: tuple[CAPContextSource, ...]
    context_warnings: tuple[str, ...] = ()
    canon_approved: Literal[False] = False
    image_authorized: Literal[False] = False
    production_ready: Literal[False] = False

    @model_validator(mode="after")
    def verify_review_only(self) -> UnresolvedCAPReviewRecord:
        digest_args = (
            self.story_id,
            self.asset_id,
            self.story_fingerprint,
            self.context_fingerprint,
            self.asset_fingerprint,
            self.base_fingerprint,
            self.review,
        )
        allowed_hashes = {_review_digest(*digest_args)}
        if all(
            not getattr(field, key)
            for field in self.review.fields
            for key in _POST_V1_FIELD_PROVENANCE
        ):
            allowed_hashes.add(_review_digest(*digest_args, pre_story_provenance=True))
        if (
            self.specification_snapshot.asset_id != self.asset_id
            or self.review.asset_id != self.asset_id
            or self.review.story_fingerprint != self.story_fingerprint
            or self.review.context_fingerprint != self.context_fingerprint
            or self.base_fingerprint != self.specification_snapshot.fingerprint()
            or reviewed_canonical_attributes(self.specification_snapshot, self.review)
            or self.record_id not in allowed_hashes
            or not self.context_sources
        ):
            raise ValueError("The saved review is not a valid unresolved CAP decision")
        return self


class UnresolvedCAPReviewLedger:
    """Atomic per-decision files; never updates or deletes an older review."""

    def __init__(self, project_directory: Path) -> None:
        self.directory = project_directory / "production" / "caps" / "review_decisions"

    @staticmethod
    def _identity(story_id: str, asset_id: str) -> str:
        return hashlib.sha256(f"{story_id}|{asset_id}".encode()).hexdigest()

    def _directory_for(self, story_id: str, asset_id: str) -> Path:
        return self.directory / self._identity(story_id, asset_id)

    def list_records(self, story_id: str, asset_id: str) -> tuple[UnresolvedCAPReviewRecord, ...]:
        """Reopen saved records offline, in recorded review order."""
        directory = self._directory_for(story_id, asset_id)
        if not directory.is_dir():
            return ()
        try:
            records = []
            for path in directory.glob("*.json"):
                raw = json.loads(path.read_text(encoding="utf-8"))
                record = UnresolvedCAPReviewRecord.model_validate(raw)
                if record.record_id != _stored_review_digest(raw):
                    raise ValueError("Stored CAP decision's source audit hash does not match")
                if path.stem != record.record_id:
                    raise ValueError("Stored CAP decision filename does not match its audit hash")
                records.append(record)
        except (OSError, ValueError) as exc:
            raise ValueError("Stored CAP decision history is invalid; do not overwrite it") from exc
        if any(record.story_id != story_id or record.asset_id != asset_id for record in records):
            raise ValueError("Stored CAP review identity does not match the selected asset")
        return tuple(sorted(records, key=lambda item: (item.reviewed_at_utc, item.record_id)))

    def latest(self, story_id: str, asset_id: str) -> UnresolvedCAPReviewRecord | None:
        records = self.list_records(story_id, asset_id)
        return records[-1] if records else None

    def save(
        self,
        specification: CAPStructuredSpecification,
        review: DesignReviewPackage,
        context: CAPContextManifest,
    ) -> UnresolvedCAPReviewRecord:
        """Persist only validated all-Reject/Defer decisions, idempotently."""
        if reviewed_canonical_attributes(specification, review):
            raise ValueError("Accepted or edited CAP attributes require Draft specification review")
        if (
            review.asset_id != context.asset_id
            or review.story_fingerprint != context.story_fingerprint
            or review.context_fingerprint != context.fingerprint
            or not context.sources
        ):
            raise ValueError("Reviewed Story or governed Shot context is missing or stale")
        digest = _review_digest(
            context.story_id,
            context.asset_id,
            context.story_fingerprint,
            context.fingerprint,
            context.asset_fingerprint,
            specification.fingerprint(),
            review,
        )
        directory = self._directory_for(context.story_id, context.asset_id)
        path = directory / f"{digest}.json"
        if path.exists():
            existing = UnresolvedCAPReviewRecord.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            if existing.record_id != digest or existing.review != review:
                raise ValueError("Existing CAP review record has conflicting immutable contents")
            return existing
        record = UnresolvedCAPReviewRecord(
            record_id=digest,
            story_id=context.story_id,
            asset_id=context.asset_id,
            story_fingerprint=context.story_fingerprint,
            context_fingerprint=context.fingerprint,
            asset_fingerprint=context.asset_fingerprint,
            base_fingerprint=specification.fingerprint(),
            reviewed_at_utc=datetime.now(UTC).isoformat(),
            specification_snapshot=specification,
            review=review,
            context_sources=context.sources,
            context_warnings=context.warnings,
        )
        directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        try:
            temporary.write_text(record.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        return record
