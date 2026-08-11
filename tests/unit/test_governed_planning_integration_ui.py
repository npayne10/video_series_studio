"""Phase 19.3.9 Planning Review → Integration UI acceptance tests."""

from __future__ import annotations

from vscs.application.story import (
    GovernedPlanningIntegrationService,
    IntegratedPlanningPackage,
    PlanningCheckStatus,
    PlanningReview,
    PlanningReviewCheck,
    PlanningReviewSnapshot,
    PlanningReviewStatus,
    ShotPlan,
    ShotPlanStatus,
)
from vscs.presentation.widgets.governed_planning_review import GovernedPlanningReviewDialog


class FakeIntegrationService(GovernedPlanningIntegrationService):
    def __init__(self) -> None:
        self.package: IntegratedPlanningPackage | None = None

    def current_package(self, _shot_id: str) -> IntegratedPlanningPackage | None:
        return self.package

    def integrate(self, shot_id: str) -> IntegratedPlanningPackage:
        self.package = IntegratedPlanningPackage(
            package_id="PIP-SHOT-001-ABC123",
            shot_id=shot_id,
            review_id="PRV-SHOT-001",
            review_fingerprint="fingerprint",
            package_fingerprint="package-fingerprint",
            payload_json="{}",
        )
        return self.package


class FakeReviewService:
    def __init__(self) -> None:
        self.value = PlanningReview(
            review_id="PRV-SHOT-001",
            shot_id="SHOT-001",
            planning_fingerprint="fingerprint",
            status=PlanningReviewStatus.DRAFT,
        )
        self.planning_integration_service = FakeIntegrationService()

    def snapshot(self, shot_id: str) -> PlanningReviewSnapshot:
        checks = tuple(
            PlanningReviewCheck(area, PlanningCheckStatus.PASS, "Ready and current")
            for area in ("Shot", "Assets", "Camera", "Lighting", "Environment")
        )
        return PlanningReviewSnapshot(shot_id, checks, "fingerprint")

    def review(self, _shot_id: str) -> PlanningReview:
        return self.value

    def is_current(self, _review: PlanningReview) -> bool:
        return True

    def approve(self, _shot_id: str) -> PlanningReview:
        self.value = PlanningReview(
            review_id=self.value.review_id,
            shot_id=self.value.shot_id,
            planning_fingerprint=self.value.planning_fingerprint,
            status=PlanningReviewStatus.APPROVED,
        )
        return self.value

    def update_notes(self, _shot_id: str, _notes: str) -> PlanningReview:
        return self.value

    def return_to_draft(self, _shot_id: str) -> PlanningReview:
        return self.value


def _shot() -> ShotPlan:
    return ShotPlan(
        shot_id="SHOT-001",
        scene_id="SCN-001",
        sequence_number=1,
        title="Orbital reveal",
        narrative_purpose="Establish the planet.",
        production_objective="Show credible orbital scale.",
        target_runtime_seconds=8,
        required_action="Ship crosses frame.",
        scene_contract_hash="scene",
        status=ShotPlanStatus.READY,
    )


def test_approval_automatically_materializes_current_integration_package(qtbot) -> None:
    service = FakeReviewService()
    dialog = GovernedPlanningReviewDialog(
        service,  # type: ignore[arg-type]
        _shot(),
    )
    qtbot.addWidget(dialog)

    assert "Pending" in dialog.integration_status.text()
    assert dialog.approve_button.isEnabled()

    dialog.approve_button.click()

    assert "CURRENT" in dialog.integration_status.text()
    assert "PIP-SHOT-001-ABC123" in dialog.integration_status.text()
    assert service.planning_integration_service.package is not None
