"""Phase 19.3.9 planning integration service tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from vscs.application.story.planning_integration import (
    GovernedPlanningIntegrationService,
    PlanningIntegrationError,
)
from vscs.application.story.planning_review import PlanningReview, PlanningReviewStatus


@dataclass(frozen=True)
class _Plan:
    identity: str
    revision: int = 1


@dataclass(frozen=True)
class _Binding:
    binding_id: str
    shot_id: str
    production_role: str = "Primary spacecraft"


@dataclass(frozen=True)
class _Resolution:
    asset_id: str
    cap_id: str
    reference_id: str
    behaviour: tuple[str, ...]


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Planner:
    def __init__(self, identity: str) -> None:
        self.value = _Plan(identity)

    def plan(self, _shot_id: str) -> _Plan:
        return self.value


class _Assets:
    def __init__(self) -> None:
        self.binding = _Binding("BIND-001", "SHOT-001")
        self.resolution = _Resolution(
            "CAP-SHP-001",
            "CAP-SHP-001",
            "REF-MASTER-001",
            ("Maintain disciplined survey-vessel motion.",),
        )

    def list_bindings(self, *, shot_id: str) -> tuple[_Binding, ...]:
        assert shot_id == "SHOT-001"
        return (self.binding,)

    def resolved_asset(self, binding: _Binding) -> _Resolution | None:
        assert binding == self.binding
        return self.resolution


class _Reviews:
    def __init__(self) -> None:
        self.shots = _Planner("SHOT-001")
        self.assets = _Assets()
        self.camera = _Planner("CAM-001")
        self.lighting = _Planner("LGT-001")
        self.environment = _Planner("ENV-001")
        self.current = True
        self.value = PlanningReview(
            review_id="PRV-SHOT-001",
            shot_id="SHOT-001",
            planning_fingerprint="review-fingerprint-1",
            reviewer_notes="Production planning checked.",
            status=PlanningReviewStatus.APPROVED,
        )

    def review(self, shot_id: str) -> PlanningReview | None:
        return self.value if shot_id == "SHOT-001" else None

    def is_production_ready(self, review: PlanningReview) -> bool:
        return self.current and review == self.value


def _service(tmp_path: Path) -> tuple[GovernedPlanningIntegrationService, _Reviews]:
    reviews = _Reviews()
    service = GovernedPlanningIntegrationService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        reviews,  # type: ignore[arg-type]
    )
    return service, reviews


def test_requires_current_approved_planning_review(tmp_path: Path) -> None:
    service, reviews = _service(tmp_path)
    reviews.current = False

    with pytest.raises(PlanningIntegrationError, match="not Approved, current"):
        service.integrate("SHOT-001")


def test_integrates_complete_renderer_neutral_planning_payload(tmp_path: Path) -> None:
    service, _reviews = _service(tmp_path)

    package = service.integrate("shot-001")
    payload = package.payload()

    assert package.package_id.startswith("PIP-SHOT-001-")
    assert payload["shot"]["identity"] == "SHOT-001"
    assert payload["camera"]["identity"] == "CAM-001"
    assert payload["lighting"]["identity"] == "LGT-001"
    assert payload["environment"]["identity"] == "ENV-001"
    assert payload["assets"][0]["binding"]["production_role"] == "Primary spacecraft"
    assert payload["assets"][0]["resolution"]["reference_id"] == "REF-MASTER-001"
    assert payload["assets"][0]["resolution"]["behaviour"] == [
        "Maintain disciplined survey-vessel motion."
    ]
    assert "prompt" not in payload
    assert "renderer" not in payload


def test_identical_approved_planning_is_idempotent_and_persistent(tmp_path: Path) -> None:
    service, reviews = _service(tmp_path)

    first = service.integrate("SHOT-001")
    second = service.integrate("SHOT-001")
    reloaded = GovernedPlanningIntegrationService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        reviews,  # type: ignore[arg-type]
    )

    assert second == first
    assert reloaded.list_packages() == (first,)
    assert reloaded.require_current_package("SHOT-001") == first


def test_upstream_change_invalidates_current_package(tmp_path: Path) -> None:
    service, reviews = _service(tmp_path)
    package = service.integrate("SHOT-001")

    reviews.current = False

    assert not service.is_current(package)
    assert service.current_package("SHOT-001") is None
    with pytest.raises(PlanningIntegrationError, match="No current integrated"):
        service.require_current_package("SHOT-001")


def test_reapproval_creates_new_package_and_preserves_history(tmp_path: Path) -> None:
    service, reviews = _service(tmp_path)
    first = service.integrate("SHOT-001")

    reviews.shots.value = replace(reviews.shots.value, revision=2)
    reviews.value = replace(
        reviews.value,
        planning_fingerprint="review-fingerprint-2",
        reviewer_notes="Re-reviewed after Shot revision.",
    )
    second = service.integrate("SHOT-001")

    assert second.package_id != first.package_id
    assert service.list_packages(shot_id="SHOT-001") == (first, second)
    assert service.current_package("SHOT-001") == second
