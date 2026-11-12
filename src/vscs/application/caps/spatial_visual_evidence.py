"""F5.4.2 Stage B: review-only field evidence and spatial ROI proposals.

No inference, persistence, generation, attempt reservation, or CAP mutation.
Each claim is bound to a specific saved Candidate review and accepted CAP field.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from vscs.application.caps.general_visual_correction_triage import (
    VisualCorrectionTriage,
)
from vscs.application.caps.geometry_correction_policy import (
    GeometryCorrectionError,
    GeometryDefect,
    _ALLOWED_STAGES,
)


class VisualEvidenceStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"
    VERIFIED_BY_OPERATOR = "VERIFIED_BY_OPERATOR"


@dataclass(frozen=True, slots=True)
class NormalizedRegion:
    """Operator-proposed rectangular region in source-image-relative coordinates."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if (
            any(type(v) not in (float, int) or not math.isfinite(v) for v in values)
            or not 0 <= self.x < 1
            or not 0 <= self.y < 1
            or not 0 < self.width <= 1
            or not 0 < self.height <= 1
            or self.x + self.width > 1 + 1e-9
            or self.y + self.height > 1 + 1e-9
        ):
            raise GeometryCorrectionError("ROI must be a finite rectangle within [0,1]")


@dataclass(frozen=True, slots=True)
class ReviewedVisualEvidence:
    field: str
    requirement: str
    status: VisualEvidenceStatus
    observation: str
    defect: GeometryDefect | None
    proposed_region: NormalizedRegion | None
    region_reviewer_confirmed: bool
    correction_stages: tuple[str, ...]

    @property
    def region_ready_for_review(self) -> bool:
        return self.status is VisualEvidenceStatus.FAILED and self.proposed_region is not None


@dataclass(frozen=True, slots=True)
class SpatialEvidenceReview:
    asset_id: str
    reference_id: int
    source_sha256: str
    reviewed_fields: tuple[ReviewedVisualEvidence, ...]
    advisory_violations: tuple[str, ...]
    source_review_decision: str
    gpu_execution_authorized: bool = False
    cap_registration_allowed: bool = False
    canon_approval_allowed: bool = False
    governed_attempt_allowed: bool = False

    @property
    def outstanding_fields(self) -> int:
        return sum(item.status is VisualEvidenceStatus.UNKNOWN for item in self.reviewed_fields)

    def describe(self) -> str:
        lines = [
            "F5.4.2 STAGE B - STRUCTURED SPATIAL EVIDENCE (REVIEW ONLY)",
            f"Asset: {self.asset_id} | Candidate: {self.reference_id}",
            f"Bound source SHA-256: {self.source_sha256}",
            f"Saved decision (advisory): {self.source_review_decision}",
            "Every accepted CAP field must be independently assessed.",
        ]
        for item in self.reviewed_fields:
            lines.append(f"{item.field}: {item.status.value} — {item.requirement}")
            if item.observation:
                lines.append(f"  Operator evidence: {item.observation}")
            if item.proposed_region is not None:
                region = item.proposed_region
                lines.append(
                    f"  Proposed ROI (normalized): x={region.x:.3f}, y={region.y:.3f}, "
                    f"w={region.width:.3f}, h={region.height:.3f}"
                )
                lines.append("  ROI IS A PROPOSAL, NOT A VERIFIED MASK")
            if item.correction_stages:
                lines.append(f"  Advisory correction route: {' -> '.join(item.correction_stages)}")
        lines.append("Semantic findings remain advisory, not accepted design:")
        lines.extend(self.advisory_violations or ("  (none recorded)",))
        lines.extend(
            (
                "No ROI-to-mask conversion, API call, generation, approval,",
                "CAP write, or governed attempt reservation is authorized.",
            )
        )
        return "\n".join(lines)


def propose_spatial_evidence(
    triage: VisualCorrectionTriage,
    *,
    field: str | None = None,
    status: VisualEvidenceStatus = VisualEvidenceStatus.UNKNOWN,
    observation: str = "",
    defect: GeometryDefect | None = None,
    region: NormalizedRegion | None = None,
    expected_source_sha256: str | None = None,
    previous: SpatialEvidenceReview | None = None,
) -> SpatialEvidenceReview:
    """Build an immutable in-memory proposal against one accepted field.

    The proposal is NOT persisted, an accepted semantic pass, or an approved mask.
    A later stage must separately review masks and authorize any generation.
    """
    if expected_source_sha256 is not None and expected_source_sha256 != triage.image_sha256:
        raise GeometryCorrectionError("Spatial evidence source hash mismatch")
    if previous is not None:
        if (
            previous.asset_id != triage.asset_id
            or previous.reference_id != triage.reference_id
            or previous.source_sha256 != triage.image_sha256
            or tuple((item.field, item.requirement) for item in previous.reviewed_fields)
            != tuple((check.field, check.requirement) for check in triage.mandatory_checks)
        ):
            raise GeometryCorrectionError("Prior spatial review is stale or unbound")
    if not isinstance(status, VisualEvidenceStatus):
        raise GeometryCorrectionError("Unsupported field verification status")
    if field is None:
        if status is not VisualEvidenceStatus.UNKNOWN or observation or defect or region:
            raise GeometryCorrectionError("Evidence must bind to a reviewed CAP field")
    elif field not in {c.field for c in triage.mandatory_checks}:
        raise GeometryCorrectionError("Evidence must bind to a reviewed CAP field")
    if not isinstance(observation, str) or len(observation) > 2000:
        raise GeometryCorrectionError("Evidence text exceeds 2000 characters")
    if region is not None and not isinstance(region, NormalizedRegion):
        raise GeometryCorrectionError("ROI must be a valid normalized region")
    if field is not None:
        if status is VisualEvidenceStatus.UNKNOWN:
            if observation.strip() or defect is not None or region is not None:
                raise GeometryCorrectionError("Unknown field cannot contain asserted evidence")
        elif status is VisualEvidenceStatus.VERIFIED_BY_OPERATOR:
            if not 12 <= len(observation.strip()) <= 2000 or defect is not None or region is not None:
                raise GeometryCorrectionError("Verified field requires operator evidence, not a defect or ROI")
        elif status is VisualEvidenceStatus.FAILED:
            if (
                not 12 <= len(observation.strip()) <= 2000
                or not isinstance(defect, GeometryDefect)
            ):
                raise GeometryCorrectionError("Failed field requires observed defect and evidence")
    checks = []
    prior_fields = (
        {item.field: item for item in previous.reviewed_fields}
        if previous is not None
        else {}
    )
    for check in triage.mandatory_checks:
        if field != check.field and check.field in prior_fields:
            checks.append(prior_fields[check.field])
            continue
        selected = check.field == field
        selected_status = status if selected else VisualEvidenceStatus.UNKNOWN
        selected_defect = defect if selected else None
        checks.append(
            ReviewedVisualEvidence(
                field=check.field,
                requirement=check.requirement,
                status=selected_status,
                observation=observation.strip() if selected else "",
                defect=selected_defect,
                proposed_region=region if selected else None,
                region_reviewer_confirmed=False,
                correction_stages=(
                    tuple(stage.value for stage in _ALLOWED_STAGES[selected_defect])
                    if selected_defect is not None
                    else ()
                ),
            )
        )
    return SpatialEvidenceReview(
        asset_id=triage.asset_id,
        reference_id=triage.reference_id,
        source_sha256=triage.image_sha256,
        reviewed_fields=tuple(checks),
        advisory_violations=triage.advisory_violations,
        source_review_decision=triage.quality_decision,
    )
