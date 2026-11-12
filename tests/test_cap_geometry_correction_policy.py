"""F5.4.1D general-purpose, no-GPU visual geometry correction planning."""

import json

import pytest

from vscs.application.caps.geometry_correction_policy import (
    CorrectionStage,
    GeometryCorrectionError,
    GeometryDefect,
    advance_after_review,
    inspect_repair_plan,
    prepare_repair_plan,
    record_stage_assessment,
    write_repair_plan_once,
)

SOURCE = "a" * 64
MASK = "b" * 64


def _plan(defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED):
    return prepare_repair_plan(
        defect=defect,
        asset_kind="diagnostic_console",
        asset_id="STORY-PRO-B00D168E43",
        reviewed_requirement="A recessed rotary dial to the right of three buttons",
        observed_failure="A circular cavity exists but its dial is absent",
        source_sha256=SOURCE,
        mask_sha256=MASK,
        source_lineage="isolated F5.4.1C run_003 output - not a CAP Candidate",
    )


@pytest.mark.parametrize("defect", list(GeometryDefect))
def test_each_defect_receives_reviewed_bounded_stage_policy(defect):
    plan = _plan(defect)
    assert plan.stages
    assert plan.stages[-1] == CorrectionStage.VERIFY_DESIGN.value
    assert plan.max_new_gpu_attempts == 1
    assert plan.generated_gpu_attempts == 0
    assert not plan.can_request_gpu
    assert not plan.can_advance
    assert not plan.cap_registration_allowed
    assert not plan.canon_approval_allowed
    assert not plan.governed_attempt_consumption_allowed


def test_cavity_with_missing_dial_is_component_reconstruction_not_repeat_cavity():
    plan = _plan(GeometryDefect.MISSING_COMPONENT)
    assert plan.stages == (
        "reconstruct_component",
        "verify_design",
    )
    assert "absent" in plan.observed_failure
    assert plan.source_lineage.endswith("not a CAP Candidate")


def test_failed_geometry_review_consumes_one_disposable_budget_and_cannot_advance():
    plan = _plan(GeometryDefect.MISSING_COMPONENT)
    reviewed = record_stage_assessment(
        plan,
        source_sha256=SOURCE,
        mask_sha256=MASK,
        outside_mask_pixels_identical=True,
        geometry_accepted=False,
        reviewer_confirmed=True,
        new_gpu_attempts_used=1,
    )
    assert not reviewed.can_advance
    assert reviewed.generated_gpu_attempts == 1
    with pytest.raises(GeometryCorrectionError, match="unverified"):
        advance_after_review(reviewed)
    with pytest.raises(GeometryCorrectionError, match="budget exhausted"):
        record_stage_assessment(
            reviewed,
            source_sha256=SOURCE,
            mask_sha256=MASK,
            outside_mask_pixels_identical=True,
            geometry_accepted=False,
            reviewer_confirmed=True,
            new_gpu_attempts_used=1,
        )


def test_human_accepted_stage_can_advance_but_never_authorize_generation():
    plan = _plan(GeometryDefect.MISSING_COMPONENT)
    reviewed = record_stage_assessment(
        plan,
        source_sha256=SOURCE,
        mask_sha256=MASK,
        outside_mask_pixels_identical=True,
        geometry_accepted=True,
        reviewer_confirmed=True,
        new_gpu_attempts_used=1,
    )
    assert reviewed.can_advance
    next_plan = advance_after_review(reviewed)
    assert next_plan.current_stage == 1
    assert next_plan.stages[next_plan.current_stage] == "verify_design"
    assert not next_plan.can_request_gpu
    assert next_plan.outside_mask_pixels_identical is None
    assert not next_plan.can_advance


def test_hash_mismatch_and_spatial_failures_reject_progression():
    plan = _plan(GeometryDefect.MISSING_COMPONENT)
    with pytest.raises(GeometryCorrectionError, match="Source lineage"):
        record_stage_assessment(
            plan,
            source_sha256="c" * 64,
            mask_sha256=MASK,
            outside_mask_pixels_identical=True,
            geometry_accepted=True,
            reviewer_confirmed=True,
            new_gpu_attempts_used=0,
        )
    with pytest.raises(GeometryCorrectionError, match="protected pixels"):
        record_stage_assessment(
            plan,
            source_sha256=SOURCE,
            mask_sha256=MASK,
            outside_mask_pixels_identical=False,
            geometry_accepted=True,
            reviewer_confirmed=True,
            new_gpu_attempts_used=0,
        )


def test_sealed_plan_read_write_once_no_overwrite(tmp_path):
    plan = _plan(GeometryDefect.MISSING_COMPONENT)
    path = tmp_path / "geometry_repair_plan.json"
    digest = write_repair_plan_once(path, plan)
    loaded = inspect_repair_plan(path, digest)
    assert loaded == plan
    with pytest.raises(GeometryCorrectionError, match="must be new"):
        write_repair_plan_once(path, plan)
    path.write_text(json.dumps({"tampered": True}))
    with pytest.raises(GeometryCorrectionError, match="checksum mismatch"):
        inspect_repair_plan(path, digest)


def test_bad_defect_invalid_hash_and_budget_fail_closed():
    with pytest.raises(GeometryCorrectionError, match="Unknown"):
        _plan("arbitrary defect")
    with pytest.raises(GeometryCorrectionError, match="Only one"):
        prepare_repair_plan(
            defect=GeometryDefect.MISSING_COMPONENT,
            asset_kind="console",
            asset_id="asset",
            reviewed_requirement="required dial",
            observed_failure="missing dial",
            source_sha256=SOURCE,
            mask_sha256=MASK,
            source_lineage="isolated",
            max_new_gpu_attempts=3,
        )
