"""Governed production-planning review gate for Phase 19.3.8."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService

from .asset_resolver import GovernedAssetResolutionService
from .camera_planning import GovernedCameraPlanningService
from .environment_planning import GovernedEnvironmentPlanningService
from .lighting_planning import GovernedLightingPlanningService
from .shot_planning import GovernedShotPlanningService


class PlanningReviewError(RuntimeError):
    """Raised when a governed Planning Review cannot be processed safely."""


class PlanningReviewStatus(StrEnum):
    """Human governance state for a complete Shot planning package."""

    DRAFT = "draft"
    APPROVED = "approved"


class PlanningCheckStatus(StrEnum):
    """Result of one deterministic planning-review check."""

    PASS = "pass"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class PlanningReviewCheck:
    """One explicit review result for an authoritative planning contract."""

    area: str
    status: PlanningCheckStatus
    detail: str


@dataclass(frozen=True, slots=True)
class PlanningReviewSnapshot:
    """Current deterministic readiness view for one governed Shot."""

    shot_id: str
    checks: tuple[PlanningReviewCheck, ...]
    planning_fingerprint: str

    @property
    def is_ready(self) -> bool:
        return bool(self.checks) and all(
            check.status is PlanningCheckStatus.PASS for check in self.checks
        )

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(
            f"{check.area}: {check.detail}"
            for check in self.checks
            if check.status is PlanningCheckStatus.BLOCKED
        )


@dataclass(frozen=True, slots=True)
class PlanningReview:
    """Human approval record over one complete, renderer-neutral Shot plan."""

    review_id: str
    shot_id: str
    planning_fingerprint: str
    reviewer_notes: str = ""
    status: PlanningReviewStatus = PlanningReviewStatus.DRAFT


class GovernedPlanningReviewService:
    """Review and approve complete Shot planning without owning upstream plans."""

    FILE_NAME = "planning_reviews.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        shots: GovernedShotPlanningService,
        assets: GovernedAssetResolutionService,
        camera: GovernedCameraPlanningService,
        lighting: GovernedLightingPlanningService,
        environment: GovernedEnvironmentPlanningService,
    ) -> None:
        self.projects = projects
        self.shots = shots
        self.assets = assets
        self.camera = camera
        self.lighting = lighting
        self.environment = environment

    @property
    def planning_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "planning" / self.FILE_NAME

    def list_reviews(self) -> tuple[PlanningReview, ...]:
        path = self.planning_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            reviews = tuple(self._from_dict(item) for item in raw.get("planning_reviews", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise PlanningReviewError(f"Unable to load Planning Reviews: {exc}") from exc
        return tuple(sorted(reviews, key=lambda review: review.shot_id))

    def review(self, shot_id: str) -> PlanningReview | None:
        normalized = shot_id.strip().upper()
        return next((item for item in self.list_reviews() if item.shot_id == normalized), None)

    def snapshot(self, shot_id: str) -> PlanningReviewSnapshot:
        """Evaluate every authoritative Phase 19.3 Shot-level planning contract."""
        normalized = shot_id.strip().upper()
        shot = self.shots.plan(normalized)
        checks: list[PlanningReviewCheck] = []
        payload: dict[str, Any] = {"shot_id": normalized}

        shot_ready = shot is not None and self.shots.is_production_ready(shot)
        checks.append(self._check("Shot", shot_ready, "Ready and current", "Missing, Draft or stale"))
        payload["shot"] = asdict(shot) if shot is not None else None

        bindings = self.assets.list_bindings(shot_id=normalized)
        assets_ready = bool(bindings) and all(self.assets.is_production_ready(item) for item in bindings)
        checks.append(
            self._check(
                "Assets",
                assets_ready,
                "All governed asset bindings are Ready and current",
                "No governed bindings or one or more bindings are Draft/stale/unresolved",
            )
        )
        payload["assets"] = [asdict(item) for item in bindings]

        camera = self.camera.plan(normalized)
        camera_ready = camera is not None and self.camera.is_production_ready(camera)
        checks.append(self._check("Camera", camera_ready, "Ready and current", "Missing, Draft or stale"))
        payload["camera"] = asdict(camera) if camera is not None else None

        lighting = self.lighting.plan(normalized)
        lighting_ready = lighting is not None and self.lighting.is_production_ready(lighting)
        checks.append(
            self._check("Lighting", lighting_ready, "Ready and current", "Missing, Draft or stale")
        )
        payload["lighting"] = asdict(lighting) if lighting is not None else None

        environment = self.environment.plan(normalized)
        environment_ready = environment is not None and self.environment.is_production_ready(environment)
        checks.append(
            self._check(
                "Environment",
                environment_ready,
                "Ready, current and physically consistent",
                "Missing, Draft, stale or physically inconsistent",
            )
        )
        payload["environment"] = asdict(environment) if environment is not None else None

        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return PlanningReviewSnapshot(normalized, tuple(checks), fingerprint)

    def create(self, shot_id: str, *, reviewer_notes: str = "") -> PlanningReview:
        normalized = shot_id.strip().upper()
        if self.review(normalized) is not None:
            raise PlanningReviewError(f"Planning Review already exists for {normalized}")
        snapshot = self.snapshot(normalized)
        review = PlanningReview(
            review_id=f"PRV-{normalized}",
            shot_id=normalized,
            planning_fingerprint=snapshot.planning_fingerprint,
            reviewer_notes=reviewer_notes.strip(),
        )
        self._write((*self.list_reviews(), review))
        return review

    def update_notes(self, shot_id: str, reviewer_notes: str) -> PlanningReview:
        current = self._require_review(shot_id)
        if current.status is PlanningReviewStatus.APPROVED:
            raise PlanningReviewError("Approved Planning Reviews must return to Draft before editing")
        snapshot = self.snapshot(current.shot_id)
        updated = replace(
            current,
            planning_fingerprint=snapshot.planning_fingerprint,
            reviewer_notes=reviewer_notes.strip(),
        )
        self._replace(updated)
        return updated

    def approve(self, shot_id: str) -> PlanningReview:
        current = self._require_review(shot_id)
        snapshot = self.snapshot(current.shot_id)
        if not snapshot.is_ready:
            raise PlanningReviewError(
                "Planning Review cannot be approved while blockers remain: "
                + "; ".join(snapshot.blockers)
            )
        approved = replace(
            current,
            planning_fingerprint=snapshot.planning_fingerprint,
            status=PlanningReviewStatus.APPROVED,
        )
        self._replace(approved)
        return approved

    def return_to_draft(self, shot_id: str) -> PlanningReview:
        current = self._require_review(shot_id)
        snapshot = self.snapshot(current.shot_id)
        draft = replace(
            current,
            planning_fingerprint=snapshot.planning_fingerprint,
            status=PlanningReviewStatus.DRAFT,
        )
        self._replace(draft)
        return draft

    def is_current(self, review: PlanningReview) -> bool:
        return review.planning_fingerprint == self.snapshot(review.shot_id).planning_fingerprint

    def is_production_ready(self, review: PlanningReview) -> bool:
        snapshot = self.snapshot(review.shot_id)
        return (
            review.status is PlanningReviewStatus.APPROVED
            and snapshot.is_ready
            and review.planning_fingerprint == snapshot.planning_fingerprint
        )

    @staticmethod
    def _check(area: str, passed: bool, success: str, failure: str) -> PlanningReviewCheck:
        return PlanningReviewCheck(
            area,
            PlanningCheckStatus.PASS if passed else PlanningCheckStatus.BLOCKED,
            success if passed else failure,
        )

    def _require_review(self, shot_id: str) -> PlanningReview:
        review = self.review(shot_id)
        if review is None:
            raise PlanningReviewError(f"No Planning Review exists for {shot_id}")
        return review

    def _replace(self, updated: PlanningReview) -> None:
        reviews = tuple(
            updated if item.review_id == updated.review_id else item for item in self.list_reviews()
        )
        self._write(reviews)

    def _write(self, reviews: tuple[PlanningReview, ...]) -> None:
        path = self.planning_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "planning_reviews": [self._to_dict(item) for item in reviews],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _to_dict(review: PlanningReview) -> dict[str, Any]:
        data = asdict(review)
        data["status"] = review.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> PlanningReview:
        return PlanningReview(
            review_id=str(data["review_id"]),
            shot_id=str(data["shot_id"]),
            planning_fingerprint=str(data["planning_fingerprint"]),
            reviewer_notes=str(data.get("reviewer_notes", "")),
            status=PlanningReviewStatus(str(data.get("status", PlanningReviewStatus.DRAFT.value))),
        )
