"""Phase 19.4.10 Production Package Review and Validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectService


class ReviewStatus(StrEnum):
    REVIEW_REQUIRED = "review-required"
    VALIDATION_FAILED = "validation-failed"
    APPROVED = "approved-for-production"
    CHANGES_REQUIRED = "changes-required"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str
    severity: str
    message: str


@dataclass(frozen=True, slots=True)
class ProductionPackageReview:
    shot_id: str
    status: ReviewStatus
    validation_passed: bool
    findings: tuple[ValidationFinding, ...]
    dependency_fingerprint: str
    reviewed_at: str
    reviewed_by: str = ""
    review_notes: str = ""


class ProductionPackageReviewService:
    """Final deterministic review gate for a compiled production package."""

    def __init__(self, projects: ProjectService, universal: Any, provider: Any) -> None:
        self.projects = projects
        self.universal = universal
        self.provider = provider

    def validate(self, shot_id: str) -> ProductionPackageReview:
        universal = self._payload(self.universal.current_compilation(shot_id))
        provider = self._payload(self.provider.current_compilation(shot_id))
        findings: list[ValidationFinding] = []
        if not universal:
            findings.append(ValidationFinding("universal.missing", "error", "Approved Universal Production Description is missing or stale."))
        if not provider:
            findings.append(ValidationFinding("provider.missing", "error", "Approved Provider compilation is missing or stale."))
        if provider and not str(provider.get("provider_id", "")).strip():
            findings.append(ValidationFinding("provider.id", "error", "Provider id is missing."))
        if provider and not str(provider.get("contract", "")).strip():
            findings.append(ValidationFinding("provider.contract", "error", "Provider contract is missing."))
        continuity = universal.get("continuity", {})
        conflicts = continuity.get("conflicts", []) if isinstance(continuity, dict) else []
        if conflicts:
            findings.append(ValidationFinding("continuity.conflicts", "error", "Continuity authority contains unresolved conflicts."))
        missing_refs = self._missing_references(universal.get("assets", []))
        if missing_refs:
            findings.append(ValidationFinding("canonical.coverage", "error", "Canonical production references are missing for: " + ", ".join(missing_refs)))
        passed = not any(item.severity == "error" for item in findings)
        return ProductionPackageReview(
            shot_id=shot_id,
            status=ReviewStatus.REVIEW_REQUIRED if passed else ReviewStatus.VALIDATION_FAILED,
            validation_passed=passed,
            findings=tuple(findings),
            dependency_fingerprint=self._fingerprint(universal, provider),
            reviewed_at=datetime.now(UTC).isoformat(),
        )

    def approve(self, shot_id: str, *, reviewed_by: str, notes: str = "") -> ProductionPackageReview:
        review = self.validate(shot_id)
        if not review.validation_passed:
            raise ValueError("Production Package cannot be approved while validation errors remain.")
        if not reviewed_by.strip():
            raise ValueError("Reviewer identity is required for production approval.")
        result = ProductionPackageReview(**{**asdict(review), "status": ReviewStatus.APPROVED, "reviewed_by": reviewed_by.strip(), "review_notes": notes.strip(), "reviewed_at": datetime.now(UTC).isoformat()})
        self._write(result)
        return result

    def require_changes(self, shot_id: str, *, reviewed_by: str, notes: str) -> ProductionPackageReview:
        review = self.validate(shot_id)
        result = ProductionPackageReview(**{**asdict(review), "status": ReviewStatus.CHANGES_REQUIRED, "reviewed_by": reviewed_by.strip(), "review_notes": notes.strip(), "reviewed_at": datetime.now(UTC).isoformat()})
        self._write(result)
        return result

    def current_review(self, shot_id: str) -> ProductionPackageReview | None:
        path = self._path(shot_id)
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        findings = tuple(ValidationFinding(**item) for item in raw.pop("findings", []))
        review = ProductionPackageReview(findings=findings, **raw)
        if review.dependency_fingerprint == self.validate(shot_id).dependency_fingerprint:
            return review
        return ProductionPackageReview(**{**asdict(review), "status": ReviewStatus.STALE, "validation_passed": False})

    @staticmethod
    def _payload(compilation: Any) -> dict[str, Any]:
        if compilation is None:
            return {}
        payload = getattr(compilation, "compiled", compilation)
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _missing_references(assets: Any) -> tuple[str, ...]:
        if not isinstance(assets, list):
            return ()
        result = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            category = str(asset.get("category", "")).strip().lower()
            if category in {"character", "location", "ship", "vehicle", "prop"} and not str(asset.get("canonical_reference", "")).strip():
                result.append(str(asset.get("asset_id", "")).strip() or "unknown-asset")
        return tuple(result)

    @staticmethod
    def _fingerprint(universal: dict[str, Any], provider: dict[str, Any]) -> str:
        raw = json.dumps({"universal": universal, "provider": provider}, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _path(self, shot_id: str) -> Path:
        root = self.projects.project_directory
        if root is None:
            raise RuntimeError("A project must be open before reviewing a Production Package.")
        directory = root / "production" / "reviews"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{shot_id}.review.json"

    def _write(self, review: ProductionPackageReview) -> None:
        path = self._path(review.shot_id)
        temp = path.with_suffix(path.suffix + ".tmp")
        payload = asdict(review)
        payload["status"] = review.status.value
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(path)
