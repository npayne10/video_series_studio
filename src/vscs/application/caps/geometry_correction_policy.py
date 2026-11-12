"""F5.4.1D: reusable, fail-closed visual geometry correction planning.

This module does not perform inference or grant CAP/Canon authority. It turns
one reviewed design defect into a bounded, source-hashed repair plan and
requires fresh evidence before any correction stage can advance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class GeometryCorrectionError(RuntimeError):
    """Visual defect cannot be safely planned or advanced."""


class GeometryDefect(StrEnum):
    PROTRUDING_INSTEAD_OF_RECESSED = "protruding_instead_of_recessed"
    MISSING_COMPONENT = "missing_component"
    INCORRECT_COMPONENT_COUNT = "incorrect_component_count"
    MERGED_OBJECTS = "merged_objects"
    WRONG_RELATIVE_POSITION = "wrong_relative_position"
    INCORRECT_PROPORTIONS = "incorrect_proportions"
    MATERIAL_MISMATCH = "material_mismatch"
    UNREVIEWED_DETAIL = "unreviewed_detail"


class CorrectionStage(StrEnum):
    ESTABLISH_GEOMETRY = "establish_geometry"
    RECONSTRUCT_COMPONENT = "reconstruct_component"
    VERIFY_DESIGN = "verify_design"


_ALLOWED_STAGES: dict[GeometryDefect, tuple[CorrectionStage, ...]] = {
    GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED: (
        CorrectionStage.ESTABLISH_GEOMETRY,
        CorrectionStage.RECONSTRUCT_COMPONENT,
        CorrectionStage.VERIFY_DESIGN,
    ),
    GeometryDefect.MISSING_COMPONENT: (
        CorrectionStage.RECONSTRUCT_COMPONENT,
        CorrectionStage.VERIFY_DESIGN,
    ),
    GeometryDefect.INCORRECT_COMPONENT_COUNT: (
        CorrectionStage.RECONSTRUCT_COMPONENT,
        CorrectionStage.VERIFY_DESIGN,
    ),
    GeometryDefect.MERGED_OBJECTS: (
        CorrectionStage.ESTABLISH_GEOMETRY,
        CorrectionStage.VERIFY_DESIGN,
    ),
    GeometryDefect.WRONG_RELATIVE_POSITION: (
        CorrectionStage.ESTABLISH_GEOMETRY,
        CorrectionStage.VERIFY_DESIGN,
    ),
    GeometryDefect.INCORRECT_PROPORTIONS: (
        CorrectionStage.ESTABLISH_GEOMETRY,
        CorrectionStage.VERIFY_DESIGN,
    ),
    GeometryDefect.MATERIAL_MISMATCH: (
        CorrectionStage.RECONSTRUCT_COMPONENT,
        CorrectionStage.VERIFY_DESIGN,
    ),
    GeometryDefect.UNREVIEWED_DETAIL: (
        CorrectionStage.VERIFY_DESIGN,
    ),
}


@dataclass(frozen=True, slots=True)
class GeometryRepairPlan:
    schema_version: int
    defect: str
    asset_kind: str
    asset_id: str
    reviewed_requirement: str
    observed_failure: str
    source_sha256: str
    mask_sha256: str
    source_lineage: str
    stages: tuple[str, ...]
    current_stage: int
    max_new_gpu_attempts: int
    generated_gpu_attempts: int
    outside_mask_pixels_identical: bool | None
    stage_result_accepted: bool
    reviewer_confirmed: bool
    automated_semantic_approval: bool = False
    cap_registration_allowed: bool = False
    canon_approval_allowed: bool = False
    governed_attempt_consumption_allowed: bool = False

    @property
    def can_advance(self) -> bool:
        return (
            self.reviewer_confirmed
            and self.stage_result_accepted
            and self.outside_mask_pixels_identical is True
            and self.current_stage + 1 < len(self.stages)
        )

    @property
    def can_request_gpu(self) -> bool:
        # A plan is an offline proposal, never an execution authorization.
        return False


def _checked_sha(value: str) -> str:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise GeometryCorrectionError("Expected a lowercase 64-character SHA-256 digest")
    return value


def prepare_repair_plan(
    *,
    defect: GeometryDefect,
    asset_kind: str,
    asset_id: str,
    reviewed_requirement: str,
    observed_failure: str,
    source_sha256: str,
    mask_sha256: str,
    source_lineage: str,
    max_new_gpu_attempts: int = 1,
) -> GeometryRepairPlan:
    """Compile a review-first correction sequence, not editable prompt prose."""
    if not isinstance(defect, GeometryDefect):
        raise GeometryCorrectionError("Unknown defect type")
    fields = (asset_kind, asset_id, reviewed_requirement, observed_failure, source_lineage)
    if any(not isinstance(v, str) or not v.strip() or len(v) > 2048 for v in fields):
        raise GeometryCorrectionError("Repair plan requires bounded reviewed evidence")
    if max_new_gpu_attempts != 1:
        raise GeometryCorrectionError("Only one new disposable GPU experiment is budgeted")
    return GeometryRepairPlan(
        schema_version=1,
        defect=defect.value,
        asset_kind=asset_kind.strip(),
        asset_id=asset_id.strip(),
        reviewed_requirement=reviewed_requirement.strip(),
        observed_failure=observed_failure.strip(),
        source_sha256=_checked_sha(source_sha256),
        mask_sha256=_checked_sha(mask_sha256),
        source_lineage=source_lineage.strip(),
        stages=tuple(stage.value for stage in _ALLOWED_STAGES[defect]),
        current_stage=0,
        max_new_gpu_attempts=1,
        generated_gpu_attempts=0,
        outside_mask_pixels_identical=None,
        stage_result_accepted=False,
        reviewer_confirmed=False,
    )


def record_stage_assessment(
    plan: GeometryRepairPlan,
    *,
    source_sha256: str,
    mask_sha256: str,
    outside_mask_pixels_identical: bool,
    geometry_accepted: bool,
    reviewer_confirmed: bool,
    new_gpu_attempts_used: int,
) -> GeometryRepairPlan:
    """Offline review: explicit pass evidence required for stage progression."""
    if _checked_sha(source_sha256) != plan.source_sha256:
        raise GeometryCorrectionError("Source lineage hash mismatch")
    if _checked_sha(mask_sha256) != plan.mask_sha256:
        raise GeometryCorrectionError("Mask evidence hash mismatch")
    if type(new_gpu_attempts_used) is not int or new_gpu_attempts_used < 0:
        raise GeometryCorrectionError("GPU attempt count invalid")
    if plan.generated_gpu_attempts + new_gpu_attempts_used > plan.max_new_gpu_attempts:
        raise GeometryCorrectionError("Experimental GPU budget exhausted")
    if type(outside_mask_pixels_identical) is not bool:
        raise GeometryCorrectionError("Outside-mask preservation must be explicitly measured")
    if type(geometry_accepted) is not bool or type(reviewer_confirmed) is not bool:
        raise GeometryCorrectionError("A reviewer decision and outcome are required")
    if geometry_accepted and not outside_mask_pixels_identical:
        raise GeometryCorrectionError("Cannot accept geometry when protected pixels changed")
    from dataclasses import replace

    return replace(
        plan,
        generated_gpu_attempts=plan.generated_gpu_attempts + new_gpu_attempts_used,
        outside_mask_pixels_identical=outside_mask_pixels_identical,
        stage_result_accepted=geometry_accepted,
        reviewer_confirmed=reviewer_confirmed,
    )


def advance_after_review(plan: GeometryRepairPlan) -> GeometryRepairPlan:
    """Advance approved planning stages, never run a model automatically."""
    if not plan.can_advance:
        raise GeometryCorrectionError("Cannot advance an unverified geometry correction")
    from dataclasses import replace

    return replace(
        plan,
        current_stage=plan.current_stage + 1,
        outside_mask_pixels_identical=None,
        stage_result_accepted=False,
        reviewer_confirmed=False,
    )


def write_repair_plan_once(path: Path, plan: GeometryRepairPlan) -> str:
    """Exclusive, canonical JSON evidence. No overwrite of previous experiments."""
    if path.is_symlink() or path.exists() or not path.parent.is_dir():
        raise GeometryCorrectionError("Repair plan path must be new in an existing directory")
    raw = (json.dumps(asdict(plan), sort_keys=True, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
    return hashlib.sha256(raw).hexdigest()


def inspect_repair_plan(path: Path, expected_sha256: str) -> GeometryRepairPlan:
    """Verify sealed plan and enum-derived stage path before trusting evidence."""
    if not path.is_file() or path.is_symlink() or hashlib.sha256(
        path.read_bytes()
    ).hexdigest() != _checked_sha(expected_sha256):
        raise GeometryCorrectionError("Repair plan missing or checksum mismatch")
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("not object")
        plan = GeometryRepairPlan(**value)
        defect = GeometryDefect(plan.defect)
    except (ValueError, TypeError, KeyError) as exc:
        raise GeometryCorrectionError("Malformed sealed repair plan") from exc
    if (
        plan.schema_version != 1
        or plan.stages != tuple(stage.value for stage in _ALLOWED_STAGES[defect])
        and plan.stages != [stage.value for stage in _ALLOWED_STAGES[defect]]
        or not 0 <= plan.current_stage < len(plan.stages)
        or plan.max_new_gpu_attempts != 1
        or not 0 <= plan.generated_gpu_attempts <= 1
        or plan.automated_semantic_approval
        or plan.cap_registration_allowed
        or plan.canon_approval_allowed
        or plan.governed_attempt_consumption_allowed
    ):
        raise GeometryCorrectionError("Repair plan governance or stage contract invalid")
    return plan
