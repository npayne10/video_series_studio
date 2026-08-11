"""Materialize approved Phase 19.3 planning into immutable production inputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService

from .planning_review import GovernedPlanningReviewService, PlanningReview


class PlanningIntegrationError(RuntimeError):
    """Raised when approved planning cannot be integrated safely."""


@dataclass(frozen=True, slots=True)
class IntegratedPlanningPackage:
    """Immutable renderer-neutral snapshot handed from Planning to compilation."""

    package_id: str
    shot_id: str
    review_id: str
    review_fingerprint: str
    package_fingerprint: str
    payload_json: str

    def payload(self) -> dict[str, Any]:
        """Return a detached decoded copy of the canonical planning payload."""
        decoded = json.loads(self.payload_json)
        if not isinstance(decoded, dict):
            raise PlanningIntegrationError("Integrated planning payload is not a JSON object")
        return decoded


class GovernedPlanningIntegrationService:
    """Create stable integration packages from approved governed planning."""

    FILE_NAME = "integrated_planning_packages.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        reviews: GovernedPlanningReviewService,
    ) -> None:
        self.projects = projects
        self.reviews = reviews

    @property
    def planning_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "planning" / self.FILE_NAME

    def list_packages(self, *, shot_id: str | None = None) -> tuple[IntegratedPlanningPackage, ...]:
        path = self.planning_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            packages = tuple(
                self._from_dict(item) for item in raw.get("integrated_planning_packages", [])
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise PlanningIntegrationError(
                f"Unable to load integrated Planning Packages: {exc}"
            ) from exc
        if shot_id is not None:
            normalized = shot_id.strip().upper()
            packages = tuple(item for item in packages if item.shot_id == normalized)
        return packages

    def integrate(self, shot_id: str) -> IntegratedPlanningPackage:
        """Materialize the current approved review; identical input is idempotent."""
        normalized = shot_id.strip().upper()
        review = self.reviews.review(normalized)
        if review is None:
            raise PlanningIntegrationError(f"No Planning Review exists for {normalized}")
        if not self.reviews.is_production_ready(review):
            raise PlanningIntegrationError(
                f"Planning Review for {normalized} is not Approved, current and production-ready"
            )

        payload_json = self._canonical_payload(review)
        package_fingerprint = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        package_id = f"PIP-{normalized}-{package_fingerprint[:12].upper()}"
        existing = next(
            (
                item
                for item in self.list_packages(shot_id=normalized)
                if item.package_fingerprint == package_fingerprint
            ),
            None,
        )
        if existing is not None:
            return existing

        package = IntegratedPlanningPackage(
            package_id=package_id,
            shot_id=normalized,
            review_id=review.review_id,
            review_fingerprint=review.planning_fingerprint,
            package_fingerprint=package_fingerprint,
            payload_json=payload_json,
        )
        self._write((*self.list_packages(), package))
        return package

    def current_package(self, shot_id: str) -> IntegratedPlanningPackage | None:
        """Return the package matching the currently approved planning authority."""
        normalized = shot_id.strip().upper()
        review = self.reviews.review(normalized)
        if review is None or not self.reviews.is_production_ready(review):
            return None
        expected_payload = self._canonical_payload(review)
        expected_hash = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
        return next(
            (
                item
                for item in reversed(self.list_packages(shot_id=normalized))
                if item.package_fingerprint == expected_hash
                and item.review_fingerprint == review.planning_fingerprint
            ),
            None,
        )

    def require_current_package(self, shot_id: str) -> IntegratedPlanningPackage:
        """Provide the stable Phase 19.4 handoff or fail with an explicit blocker."""
        package = self.current_package(shot_id)
        if package is None:
            raise PlanningIntegrationError(
                f"No current integrated Planning Package exists for {shot_id.strip().upper()}"
            )
        return package

    def is_current(self, package: IntegratedPlanningPackage) -> bool:
        current = self.current_package(package.shot_id)
        return current is not None and current.package_id == package.package_id

    def _canonical_payload(self, review: PlanningReview) -> str:
        shot = self.reviews.shots.plan(review.shot_id)
        camera = self.reviews.camera.plan(review.shot_id)
        lighting = self.reviews.lighting.plan(review.shot_id)
        environment = self.reviews.environment.plan(review.shot_id)
        bindings = self.reviews.assets.list_bindings(shot_id=review.shot_id)
        if shot is None or camera is None or lighting is None or environment is None:
            raise PlanningIntegrationError(
                f"Approved review {review.review_id} has missing authoritative planning data"
            )

        asset_payload: list[dict[str, Any]] = []
        for binding in bindings:
            resolved = self.reviews.assets.resolution(binding)
            if resolved is None:
                raise PlanningIntegrationError(
                    f"Approved asset binding {binding.binding_id} no longer resolves"
                )
            asset_payload.append(
                {
                    "binding": asdict(binding),
                    "resolution": asdict(resolved),
                }
            )

        payload: dict[str, Any] = {
            "schema_version": self.SCHEMA_VERSION,
            "shot_id": review.shot_id,
            "review": {
                "review_id": review.review_id,
                "planning_fingerprint": review.planning_fingerprint,
                "reviewer_notes": review.reviewer_notes,
                "status": review.status.value,
            },
            "shot": asdict(shot),
            "assets": asset_payload,
            "camera": asdict(camera),
            "lighting": asdict(lighting),
            "environment": asdict(environment),
        }
        return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))

    def _write(self, packages: tuple[IntegratedPlanningPackage, ...]) -> None:
        path = self.planning_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "integrated_planning_packages": [self._to_dict(item) for item in packages],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _to_dict(package: IntegratedPlanningPackage) -> dict[str, str]:
        return {
            "package_id": package.package_id,
            "shot_id": package.shot_id,
            "review_id": package.review_id,
            "review_fingerprint": package.review_fingerprint,
            "package_fingerprint": package.package_fingerprint,
            "payload_json": package.payload_json,
        }

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> IntegratedPlanningPackage:
        return IntegratedPlanningPackage(
            package_id=str(data["package_id"]),
            shot_id=str(data["shot_id"]),
            review_id=str(data["review_id"]),
            review_fingerprint=str(data["review_fingerprint"]),
            package_fingerprint=str(data["package_fingerprint"]),
            payload_json=str(data["payload_json"]),
        )
