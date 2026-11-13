"""F5.4.2 Stage C1: sealed, non-executable Stage B-to-correction handoff.

A reviewed ROI is a human-approved *proposal*, never a mask, ComfyUI
capability assertion, attempt reservation, or CAP/Canon registration authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from vscs.application.caps.geometry_correction_policy import (
    _ALLOWED_STAGES,
    GeometryCorrectionError,
    GeometryDefect,
)
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    SpatialEvidenceReview,
    VisualEvidenceStatus,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class GovernedCorrectionProposal:
    schema_version: int
    asset_id: str
    source_reference_id: int
    source_sha256: str
    accepted_fields: tuple[tuple[str, str], ...]
    target_field: str
    reviewed_requirement: str
    defect: GeometryDefect
    observed_failure: str
    reviewed_roi: NormalizedRegion
    stages: tuple[str, ...]
    proposal_sha256: str
    region_reviewed_by_operator: bool = True
    mask_verified: bool = False
    outside_mask_pixels_verified: bool = False
    provider_mask_capability_verified: bool = False
    gpu_execution_authorized: bool = False
    candidate_registration_allowed: bool = False
    cap_registration_allowed: bool = False
    canon_approval_allowed: bool = False
    governed_attempt_allowed: bool = False

    @property
    def can_generate(self) -> bool:
        return False

    def verify_seal(self) -> None:
        if self.schema_version != 1 or not _SHA256.fullmatch(self.source_sha256):
            raise GeometryCorrectionError("Stage C correction identity is invalid")
        if self.stages != tuple(stage.value for stage in _ALLOWED_STAGES[self.defect]):
            raise GeometryCorrectionError("Stage C correction stages changed")
        if self.reviewed_requirement != dict(self.accepted_fields).get(self.target_field):
            raise GeometryCorrectionError("Stage C target no longer matches CAP requirements")
        if (
            not self.region_reviewed_by_operator
            or self.mask_verified
            or self.outside_mask_pixels_verified
            or self.provider_mask_capability_verified
            or self.gpu_execution_authorized
            or self.candidate_registration_allowed
            or self.cap_registration_allowed
            or self.canon_approval_allowed
            or self.governed_attempt_allowed
        ):
            raise GeometryCorrectionError("Stage C handoff cannot grant production authority")
        if self.proposal_sha256 != _seal(self):
            raise GeometryCorrectionError("Stage C evidence seal mismatch")

    def describe(self) -> str:
        self.verify_seal()
        roi = self.reviewed_roi
        return "\n".join(
            (
                "F5.4.2 STAGE C1 - GOVERNED CORRECTION PROPOSAL (NO GENERATION)",
                f"Asset: {self.asset_id} | Source Candidate: {self.source_reference_id}",
                f"Source SHA-256: {self.source_sha256}",
                f"Target reviewed field: {self.target_field}",
                f"Accepted requirement: {self.reviewed_requirement}",
                f"Observed failure: {self.observed_failure}",
                f"Defect: {self.defect.value}",
                f"Operator-reviewed ROI: {roi.x:.3f},{roi.y:.3f},"
                f"{roi.width:.3f},{roi.height:.3f}",
                f"Proposed stages: {' -> '.join(self.stages)}",
                f"Proposal SHA-256: {self.proposal_sha256}",
                "ROI is NOT a mask. No mask pixels or protected-pixel proof exist.",
                "Provider mask compatibility is NOT validated.",
                "No API, ComfyUI, GPU, Candidate registration, approval, or attempt reservation.",
            )
        )


def _seal(proposal: GovernedCorrectionProposal) -> str:
    roi = proposal.reviewed_roi
    payload = {
        "schema_version": proposal.schema_version,
        "asset_id": proposal.asset_id,
        "source_reference_id": proposal.source_reference_id,
        "source_sha256": proposal.source_sha256,
        "accepted_fields": proposal.accepted_fields,
        "target_field": proposal.target_field,
        "reviewed_requirement": proposal.reviewed_requirement,
        "defect": proposal.defect.value,
        "observed_failure": proposal.observed_failure,
        "roi": (roi.x, roi.y, roi.width, roi.height),
        "stages": proposal.stages,
        "region_reviewed_by_operator": proposal.region_reviewed_by_operator,
        "mask_verified": proposal.mask_verified,
        "outside_mask_pixels_verified": proposal.outside_mask_pixels_verified,
        "provider_mask_capability_verified": proposal.provider_mask_capability_verified,
        "gpu_execution_authorized": proposal.gpu_execution_authorized,
        "candidate_registration_allowed": proposal.candidate_registration_allowed,
        "cap_registration_allowed": proposal.cap_registration_allowed,
        "canon_approval_allowed": proposal.canon_approval_allowed,
        "governed_attempt_allowed": proposal.governed_attempt_allowed,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def prepare_governed_correction_proposal(
    review: SpatialEvidenceReview,
    *,
    target_field: str,
    expected_source_sha256: str,
    reviewer_confirmed_roi: bool,
) -> GovernedCorrectionProposal:
    """Convert fully reviewed Stage B evidence into an offline correction intent.

    Explicit ROI acknowledgement does not validate pixel masks or provider support.
    """
    if (
        not _SHA256.fullmatch(expected_source_sha256)
        or review.source_sha256 != expected_source_sha256
    ):
        raise GeometryCorrectionError("Stage C source identity mismatch")
    if type(review.reference_id) is not int or review.reference_id < 1:
        raise GeometryCorrectionError("Stage C Candidate identity invalid")
    if not review.asset_id.strip() or not review.reviewed_fields:
        raise GeometryCorrectionError("Stage C requires reviewed Candidate fields")
    if type(reviewer_confirmed_roi) is not bool or not reviewer_confirmed_roi:
        raise GeometryCorrectionError("Stage C requires explicit operator ROI review")
    if review.outstanding_fields:
        raise GeometryCorrectionError("All accepted CAP fields require explicit review")
    fields = review.reviewed_fields
    names = tuple(item.field for item in fields)
    if len(set(names)) != len(names) or not all(
        item.field.strip() and item.requirement.strip() for item in fields
    ):
        raise GeometryCorrectionError("Stage C accepted fields are invalid")
    failed = [item for item in fields if item.status is VisualEvidenceStatus.FAILED]
    if len(failed) != 1 or failed[0].field != target_field:
        raise GeometryCorrectionError("Stage C requires exactly one reviewed failed target")
    target = failed[0]
    if (
        not isinstance(target.defect, GeometryDefect)
        or target.proposed_region is None
        or not isinstance(target.proposed_region, NormalizedRegion)
        or target.region_reviewer_confirmed
        or not 12 <= len(target.observation.strip()) <= 2000
        or target.correction_stages
        != tuple(stage.value for stage in _ALLOWED_STAGES[target.defect])
    ):
        raise GeometryCorrectionError("Stage C target evidence or ROI invalid")
    if any(
        item.status is not VisualEvidenceStatus.VERIFIED_BY_OPERATOR
        or not 12 <= len(item.observation.strip()) <= 2000
        or item.defect is not None
        or item.proposed_region is not None
        for item in fields
        if item.field != target_field
    ):
        raise GeometryCorrectionError("Stage C non-target fields require independent review")
    accepted = tuple((item.field, item.requirement) for item in fields)
    provisional = GovernedCorrectionProposal(
        schema_version=1,
        asset_id=review.asset_id,
        source_reference_id=review.reference_id,
        source_sha256=review.source_sha256,
        accepted_fields=accepted,
        target_field=target.field,
        reviewed_requirement=target.requirement,
        defect=target.defect,
        observed_failure=target.observation,
        reviewed_roi=target.proposed_region,
        stages=target.correction_stages,
        proposal_sha256="",
    )
    from dataclasses import replace

    proposal = replace(provisional, proposal_sha256=_seal(provisional))
    proposal.verify_seal()
    return proposal
