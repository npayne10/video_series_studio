"""Human identity gate for automated character introductions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class IntroductionIdentityGateError(RuntimeError):
    """Raised when character-introduction identity governance is invalid."""


class IntroductionIdentityDecision(StrEnum):
    """Human decision for one exact synthesized introduction candidate."""

    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class IntroductionIdentityReview:
    """Human decision bound to one exact synthesized candidate image."""

    requirement_id: str
    result_id: str
    image_sha256: str
    decision: IntroductionIdentityDecision
    reviewed_by: str
    reviewed_at: str
    notes: str = ""
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in ("requirement_id", "result_id", "image_sha256", "reviewed_by", "reviewed_at"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise IntroductionIdentityGateError(
                    f"Introduction identity review requires {field_name}"
                )
            if field_name == "image_sha256":
                value = value.lower()
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "notes", self.notes.strip())

    @property
    def review_id(self) -> str:
        return f"IIR-{_fingerprint(self._authority_payload())[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "requirement_id": self.requirement_id,
            "result_id": self.result_id,
            "image_sha256": self.image_sha256,
            "decision": self.decision.value,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "notes": self.notes,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["review_id"] = self.review_id
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "IntroductionIdentityReview":
        review = cls(
            requirement_id=str(raw.get("requirement_id") or ""),
            result_id=str(raw.get("result_id") or ""),
            image_sha256=str(raw.get("image_sha256") or ""),
            decision=IntroductionIdentityDecision(str(raw.get("decision") or "")),
            reviewed_by=str(raw.get("reviewed_by") or ""),
            reviewed_at=str(raw.get("reviewed_at") or ""),
            notes=str(raw.get("notes") or ""),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )
        supplied = str(raw.get("review_id") or "").strip()
        if supplied and supplied != review.review_id:
            raise IntroductionIdentityGateError(
                "Introduction identity review identity does not match governed content"
            )
        return review


@dataclass(frozen=True, slots=True)
class IntroductionIdentityCandidateStatus:
    """Operator-facing identity candidate and canonical-reference evidence."""

    requirement_id: str
    result_id: str
    image_path: str
    image_sha256: str
    introduced_asset_ids: tuple[str, ...]
    introduced_reference_ids: tuple[str, ...]
    introduced_reference_paths: tuple[str, ...]
    introduced_reference_sha256: tuple[str, ...]
    target_global_frame_index: int
    attempt_number: int
    decision: IntroductionIdentityDecision | None = None

    @property
    def pending(self) -> bool:
        return self.decision is None


class IntroductionIdentityReviewStore:
    """Append-only human identity review authority."""

    RELATIVE_PATH = Path(".vscs") / "introduction_identity_reviews.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.path = self.project_directory / self.RELATIVE_PATH

    def save(
        self,
        review: IntroductionIdentityReview,
    ) -> IntroductionIdentityReview:
        root = self._root()
        rows = [dict(item) for item in root.get("reviews", []) if isinstance(item, dict)]
        if not any(str(item.get("review_id") or "") == review.review_id for item in rows):
            rows.append(review.to_dict())
        root["reviews"] = rows
        self._write(root)
        stored = self.review_for_result(review.result_id)
        assert stored is not None
        return stored

    def record(
        self,
        *,
        requirement_id: str,
        result_id: str,
        image_sha256: str,
        decision: IntroductionIdentityDecision,
        reviewed_by: str,
        notes: str = "",
        reviewed_at: str | None = None,
    ) -> IntroductionIdentityReview:
        return self.save(
            IntroductionIdentityReview(
                requirement_id=requirement_id,
                result_id=result_id,
                image_sha256=image_sha256,
                decision=decision,
                reviewed_by=reviewed_by,
                reviewed_at=reviewed_at or datetime.now(UTC).isoformat(),
                notes=notes,
            )
        )

    def review_for_result(self, result_id: str) -> IntroductionIdentityReview | None:
        normalized = result_id.strip()
        for raw in reversed(self._root().get("reviews", [])):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("result_id") or "").strip() != normalized:
                continue
            return IntroductionIdentityReview.from_dict(raw)
        return None

    def approved(self, result_id: str, image_sha256: str) -> bool:
        review = self.review_for_result(result_id)
        return (
            review is not None
            and review.decision is IntroductionIdentityDecision.APPROVED
            and review.image_sha256 == image_sha256.strip().lower()
        )

    def rejected_count(self, requirement_id: str) -> int:
        normalized = requirement_id.strip()
        count = 0
        for raw in self._root().get("reviews", []):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("requirement_id") or "").strip() != normalized:
                continue
            if str(raw.get("decision") or "").strip() == IntroductionIdentityDecision.REJECTED.value:
                count += 1
        return count

    def _root(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"schema_version": "1.0", "reviews": []}
        try:
            root = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise IntroductionIdentityGateError(
                f"Cannot read introduction identity-review store: {exc}"
            ) from exc
        if not isinstance(root, dict):
            raise IntroductionIdentityGateError(
                "Introduction identity-review store root must be an object"
            )
        reviews = root.get("reviews", [])
        if not isinstance(reviews, list):
            raise IntroductionIdentityGateError(
                "Introduction identity-review store reviews must be an array"
            )
        return dict(root)

    def _write(self, root: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(root, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
