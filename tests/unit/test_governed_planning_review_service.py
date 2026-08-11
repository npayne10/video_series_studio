"""Phase 19.3.8 governed Planning Review tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from vscs.application.story.planning_review import (
    GovernedPlanningReviewService,
    PlanningReviewError,
    PlanningReviewStatus,
)


@dataclass(frozen=True)
class _Plan:
    identity: str
    revision: int = 1


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Shots:
    def __init__(self) -> None:
        self.value = _Plan("SHOT-001")
        self.ready = True

    def plan(self, _shot_id: str) -> _Plan:
        return self.value

    def is_production_ready(self, _plan: _Plan) -> bool:
        return self.ready


class _Assets:
    def __init__(self) -> None:
        self.values = [_Plan("BIND-001")]
        self.ready = True

    def list_bindings(self, *, shot_id: str) -> tuple[_Plan, ...]:
        assert shot_id == "SHOT-001"
        return tuple(self.values)

    def is_production_ready(self, _binding: _Plan) -> bool:
        return self.ready


class _SinglePlanner:
    def __init__(self, identity: str) -> None:
        self.value = _Plan(identity)
        self.ready = True

    def plan(self, _shot_id: str) -> _Plan:
        return self.value

    def is_production_ready(self, _plan: _Plan) -> bool:
        return self.ready


def _service(tmp_path: Path) -> tuple[GovernedPlanningReviewService, dict[str, Any]]:
    shots = _Shots()
    assets = _Assets()
    camera = _SinglePlanner("CAM-001")
    lighting = _SinglePlanner("LGT-001")
    environment = _SinglePlanner("ENV-001")
    service = GovernedPlanningReviewService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        shots,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        camera,  # type: ignore[arg-type]
        lighting,  # type: ignore[arg-type]
        environment,  # type: ignore[arg-type]
    )
    return service, {
        "shots": shots,
        "assets": assets,
        "camera": camera,
        "lighting": lighting,
        "environment": environment,
    }


def test_complete_planning_can_be_reviewed_and_approved(tmp_path: Path) -> None:
    service, _parts = _service(tmp_path)

    snapshot = service.snapshot("shot-001")
    assert snapshot.is_ready
    assert len(snapshot.checks) == 5

    review = service.create("shot-001", reviewer_notes="Checked against production intent.")
    assert review.status is PlanningReviewStatus.DRAFT

    approved = service.approve("shot-001")
    assert approved.status is PlanningReviewStatus.APPROVED
    assert service.is_production_ready(approved)

    reloaded = service.review("SHOT-001")
    assert reloaded == approved


def test_blocker_prevents_approval(tmp_path: Path) -> None:
    service, parts = _service(tmp_path)
    parts["lighting"].ready = False
    snapshot = service.snapshot("SHOT-001")
    assert not snapshot.is_ready
    assert any("Lighting" in blocker for blocker in snapshot.blockers)

    service.create("SHOT-001")
    with pytest.raises(PlanningReviewError, match="blockers remain"):
        service.approve("SHOT-001")


@pytest.mark.parametrize("area", ["shots", "assets", "camera", "lighting", "environment"])
def test_approved_review_becomes_stale_when_any_authority_changes(
    tmp_path: Path,
    area: str,
) -> None:
    service, parts = _service(tmp_path)
    service.create("SHOT-001")
    approved = service.approve("SHOT-001")

    target = parts[area]
    if area == "assets":
        target.values[0] = replace(target.values[0], revision=2)
    else:
        target.value = replace(target.value, revision=2)

    assert not service.is_current(approved)
    assert not service.is_production_ready(approved)


def test_approved_review_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    service, _parts = _service(tmp_path)
    service.create("SHOT-001")
    service.approve("SHOT-001")

    with pytest.raises(PlanningReviewError, match="return to Draft"):
        service.update_notes("SHOT-001", "Changed")

    draft = service.return_to_draft("SHOT-001")
    assert draft.status is PlanningReviewStatus.DRAFT
    updated = service.update_notes("SHOT-001", "Changed")
    assert updated.reviewer_notes == "Changed"
