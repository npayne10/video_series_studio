from __future__ import annotations

from vscs.application.story import (
    PlanningCheckStatus,
    PlanningReviewCheck,
    PlanningReviewSnapshot,
    ShotPlan,
    ShotPlanStatus,
)
from vscs.presentation.widgets.governed_planning_review import GovernedPlanningReviewDialog


class FakeReviewService:
    def snapshot(self, shot_id: str) -> PlanningReviewSnapshot:
        return PlanningReviewSnapshot(
            shot_id,
            (
                PlanningReviewCheck("Shot", PlanningCheckStatus.PASS, "Ready and current"),
                PlanningReviewCheck("Assets", PlanningCheckStatus.BLOCKED, "Binding is stale"),
                PlanningReviewCheck("Camera", PlanningCheckStatus.PASS, "Ready and current"),
                PlanningReviewCheck("Lighting", PlanningCheckStatus.PASS, "Ready and current"),
                PlanningReviewCheck("Environment", PlanningCheckStatus.PASS, "Ready and current"),
            ),
            "fingerprint",
        )

    def review(self, _shot_id: str):
        return None


def _shot() -> ShotPlan:
    return ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id="EP-001-SCN-001",
        sequence_number=1,
        title="Orbital arrival",
        narrative_purpose="Establish Xorix",
        production_objective="Show physically credible orbital scale",
        target_runtime_seconds=12,
        required_action="Ship crosses frame",
        scene_contract_hash="scene",
        status=ShotPlanStatus.READY,
    )


def test_planning_review_shows_all_authorities_and_blocks_approval(qtbot) -> None:
    dialog = GovernedPlanningReviewDialog(
        FakeReviewService(),  # type: ignore[arg-type]
        _shot(),
    )
    qtbot.addWidget(dialog)

    assert dialog.checks.rowCount() == 5
    assert dialog.checks.item(1, 0).text() == "Assets"
    assert dialog.checks.item(1, 1).text() == "BLOCKED"
    assert not dialog.approve_button.isEnabled()
    assert "does not edit" in dialog.summary.text()
