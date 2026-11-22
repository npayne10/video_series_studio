"""F5.4.2 Stage C1: sealed, non-executable Stage B-to-correction handoff.

A reviewed ROI is a human-approved *proposal*, never a mask, ComfyUI
capability assertion, attempt reservation, or CAP/Canon registration authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
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
    scoped_failed_fields: tuple[str, ...] = ()
    shared_atomic_constraint: str = ""
    field_source_quotes: tuple[tuple[str, str], ...] = ()
    separate_failed_fields: tuple[str, ...] = ()
    field_reviews: tuple[tuple[str, str, str], ...] = ()
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
        if self.schema_version not in (1, 2) or not _SHA256.fullmatch(self.source_sha256):
            raise GeometryCorrectionError("Stage C correction identity is invalid")
        if self.stages != tuple(stage.value for stage in _ALLOWED_STAGES[self.defect]):
            raise GeometryCorrectionError("Stage C correction stages changed")
        if self.reviewed_requirement != dict(self.accepted_fields).get(self.target_field):
            raise GeometryCorrectionError("Stage C target no longer matches CAP requirements")
        if self.schema_version == 1:
            if any(
                (
                    self.scoped_failed_fields,
                    self.shared_atomic_constraint,
                    self.field_source_quotes,
                    self.separate_failed_fields,
                    self.field_reviews,
                )
            ):
                raise GeometryCorrectionError("Legacy C1 scope cannot contain new claims")
        else:
            accepted = dict(self.accepted_fields)
            names = tuple(accepted)
            scoped = self.scoped_failed_fields
            separate = self.separate_failed_fields
            if (
                len(accepted) != len(self.accepted_fields)
                or len(self.field_reviews) != len(names)
                or tuple(field for field, _, _ in self.field_reviews) != names
                or not scoped
                or self.target_field not in scoped
                or len(set(scoped + separate)) != len(scoped) + len(separate)
                or set(scoped + separate)
                != {
                    field
                    for field, status, _ in self.field_reviews
                    if status == VisualEvidenceStatus.FAILED.value
                }
                or any(
                    status
                    not in (
                        VisualEvidenceStatus.FAILED.value,
                        VisualEvidenceStatus.VERIFIED_BY_OPERATOR.value,
                    )
                    or not 12 <= len(observation.strip()) <= 2000
                    for _, status, observation in self.field_reviews
                )
            ):
                raise GeometryCorrectionError("Stage C correlation scope is invalid")
            if len(scoped) > 1:
                if (
                    not 12 <= len(self.shared_atomic_constraint.strip()) <= 500
                    or tuple(field for field, _ in self.field_source_quotes) != scoped
                    or any(
                        len(quote.strip()) < 12 or quote.strip() not in accepted[field]
                        for field, quote in self.field_source_quotes
                    )
                ):
                    raise GeometryCorrectionError("Stage C correlated CAP source quotes invalid")
            elif self.shared_atomic_constraint or self.field_source_quotes or not separate:
                raise GeometryCorrectionError("Stage C scope requires explicit separate failures")
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
                *(
                    (f"Scoped FAILED fields: {', '.join(self.scoped_failed_fields)}",)
                    if self.schema_version == 2
                    else ()
                ),
                *(
                    (
                        f"Shared atomic constraint (operator asserted): {self.shared_atomic_constraint}",
                    )
                    if self.shared_atomic_constraint
                    else ()
                ),
                *(
                    (
                        f"Source CAP quote [{field}]: {quote}"
                        for field, quote in self.field_source_quotes
                    )
                ),
                *(
                    (
                        f"Other FAILED fields requiring separate corrections: {', '.join(self.separate_failed_fields)}",
                    )
                    if self.separate_failed_fields
                    else ()
                ),
                *(
                    (
                        f"Independent review [{field}]: {status} — {observation}"
                        for field, status, observation in self.field_reviews
                    )
                ),
                f"Accepted requirement: {self.reviewed_requirement}",
                f"Observed failure: {self.observed_failure}",
                f"Defect: {self.defect.value}",
                f"Operator-reviewed ROI: {roi.x:.3f},{roi.y:.3f},{roi.width:.3f},{roi.height:.3f}",
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
    if proposal.schema_version == 2:
        payload.update(
            {
                "scoped_failed_fields": proposal.scoped_failed_fields,
                "shared_atomic_constraint": proposal.shared_atomic_constraint,
                "field_source_quotes": proposal.field_source_quotes,
                "separate_failed_fields": proposal.separate_failed_fields,
                "field_reviews": proposal.field_reviews,
            }
        )
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def prepare_governed_correction_proposal(
    review: SpatialEvidenceReview,
    *,
    target_field: str,
    expected_source_sha256: str,
    reviewer_confirmed_roi: bool,
    correlated_field_quotes: Mapping[str, str] | None = None,
    shared_atomic_constraint: str = "",
    confirm_separate_failures: bool = False,
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
    if (
        review.gpu_execution_authorized
        or review.cap_registration_allowed
        or review.canon_approval_allowed
        or review.governed_attempt_allowed
    ):
        raise GeometryCorrectionError("Stage B review cannot grant production authority")
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
    if any(
        not isinstance(item.status, VisualEvidenceStatus)
        or item.region_reviewer_confirmed
        or (
            item.proposed_region is not None
            and not isinstance(item.proposed_region, NormalizedRegion)
        )
        for item in fields
    ):
        raise GeometryCorrectionError("Stage C review status or ROI authority is invalid")
    failed = [item for item in fields if item.status is VisualEvidenceStatus.FAILED]
    target = next((item for item in failed if item.field == target_field), None)
    if target is None:
        raise GeometryCorrectionError("Stage C requires a reviewed FAILED target")
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
        not 12 <= len(item.observation.strip()) <= 2000
        or (
            item.status is VisualEvidenceStatus.VERIFIED_BY_OPERATOR
            and (item.defect is not None or item.proposed_region is not None)
        )
        or (
            item.status is VisualEvidenceStatus.FAILED
            and (
                not isinstance(item.defect, GeometryDefect)
                or item.correction_stages
                != tuple(stage.value for stage in _ALLOWED_STAGES[item.defect])
            )
        )
        for item in fields
        if item.field != target_field
    ):
        raise GeometryCorrectionError("Stage C non-target fields require independent review")
    if correlated_field_quotes is not None and not isinstance(correlated_field_quotes, Mapping):
        raise GeometryCorrectionError("Stage C correlation evidence must be a field mapping")
    quotes = correlated_field_quotes or {}
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in quotes.items()):
        raise GeometryCorrectionError("Stage C correlation quotes must be source text")
    if quotes:
        if target_field not in quotes or len(quotes) < 2:
            raise GeometryCorrectionError(
                "Correlation must include target and another FAILED field"
            )
        scoped = tuple(item.field for item in failed if item.field in quotes)
        if len(scoped) != len(quotes) or any(
            item.defect != target.defect or item.proposed_region != target.proposed_region
            for item in failed
            if item.field in quotes
        ):
            raise GeometryCorrectionError("Correlated fields must share defect and exact ROI")
        if not 12 <= len(shared_atomic_constraint.strip()) <= 500:
            raise GeometryCorrectionError("Describe the shared atomic visual constraint")
        source_quotes = tuple((field, quotes[field].strip()) for field in scoped)
        accepted_requirements = {item.field: item.requirement for item in fields}
        if any(
            len(quote) < 12 or quote not in accepted_requirements[field]
            for field, quote in source_quotes
        ):
            raise GeometryCorrectionError("Quote the exact accepted CAP source for each field")
    else:
        if shared_atomic_constraint.strip():
            raise GeometryCorrectionError("Shared constraint needs source quotes for each field")
        scoped = (target_field,)
        source_quotes = ()
    separate = tuple(item.field for item in failed if item.field not in scoped)
    if separate and not confirm_separate_failures:
        raise GeometryCorrectionError(
            "Multiple FAILED fields require a correlated source mapping or explicit separate corrections"
        )
    if type(confirm_separate_failures) is not bool:
        raise GeometryCorrectionError("Separate failure confirmation must be explicit")
    version = 2 if len(scoped) > 1 or separate else 1
    accepted = tuple((item.field, item.requirement) for item in fields)
    provisional = GovernedCorrectionProposal(
        schema_version=version,
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
        scoped_failed_fields=scoped if version == 2 else (),
        shared_atomic_constraint=shared_atomic_constraint.strip() if version == 2 else "",
        field_source_quotes=source_quotes if version == 2 else (),
        separate_failed_fields=separate if version == 2 else (),
        field_reviews=(
            tuple((item.field, item.status.value, item.observation) for item in fields)
            if version == 2
            else ()
        ),
    )
    from dataclasses import replace

    proposal = replace(provisional, proposal_sha256=_seal(provisional))
    proposal.verify_seal()
    return proposal
