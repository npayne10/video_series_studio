from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskGovernanceError,
    ProductionTaskGovernanceService,
    ProductionTaskState,
    ProductionTaskType,
)


def _authority(*, approved: bool = True) -> ProductionTaskAuthority:
    return ProductionTaskAuthority(
        authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
        authority_id="upd-SH027",
        revision=3,
        fingerprint="upd-fingerprint-3",
        approved=approved,
        approved_by="Neill" if approved else None,
    )


def _task(**overrides: object) -> ProductionTask:
    values: dict[str, object] = {
        "task_id": "task-SH027-video",
        "production_id": "production-EP01",
        "episode_id": "EP01",
        "scene_id": "SC04",
        "shot_id": "SH027",
        "task_type": ProductionTaskType.VIDEO_GENERATION,
        "authority": _authority(),
        "capabilities": (ProductionCapability.VIDEO_GENERATION,),
        "required_inputs": ("canonical-character:CAP-CHR-001",),
        "expected_outputs": ("video/shot",),
        "provenance": (("compiler", "phase-19.6.2-pending"),),
    }
    values.update(overrides)
    return ProductionTask(**values)  # type: ignore[arg-type]


def test_production_task_is_provider_neutral_and_immutable() -> None:
    task = _task()

    assert task.task_type is ProductionTaskType.VIDEO_GENERATION
    assert task.capabilities == (ProductionCapability.VIDEO_GENERATION,)
    assert task.state is ProductionTaskState.PLANNED
    assert not hasattr(task, "provider")
    assert not hasattr(task, "workflow")

    with pytest.raises(FrozenInstanceError):
        task.task_id = "changed"  # type: ignore[misc]


def test_production_task_rejects_self_and_duplicate_dependencies() -> None:
    with pytest.raises(ValueError, match="cannot depend on itself"):
        _task(dependencies=("task-SH027-video",))

    with pytest.raises(ValueError, match="dependencies cannot contain duplicates"):
        _task(dependencies=("task-a", "task-a"))


def test_governance_requires_approved_upd_authority() -> None:
    task = _task(authority=_authority(approved=False))
    result = ProductionTaskGovernanceService().validate(task)

    assert not result.valid
    assert {issue.code for issue in result.issues} == {"authority-not-approved"}

    with pytest.raises(ProductionTaskGovernanceError, match="authority-not-approved"):
        ProductionTaskGovernanceService().require_valid(task)


def test_governance_rejects_provider_specific_execution_metadata() -> None:
    task = _task(metadata=(("provider", "comfyui"), ("workflow_id", "ltx-production")))
    result = ProductionTaskGovernanceService().validate(task)

    assert not result.valid
    assert [issue.code for issue in result.issues] == [
        "provider-specific-data",
        "provider-specific-data",
    ]


def test_phase_19_6_1_governance_owns_only_initial_planned_state() -> None:
    task = replace(_task(), state=ProductionTaskState.READY)
    result = ProductionTaskGovernanceService().validate(task)

    assert not result.valid
    assert any(issue.code == "invalid-initial-state" for issue in result.issues)
