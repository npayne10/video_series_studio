"""F5.4.2: general Candidate visual correction triage, advisory only.

Every accepted Draft field is a mandatory check, never an inferred pass.
A human explicitly selects defect and field; evaluator prose is evidence only.
"""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.caps.geometry_correction_policy import (
    _ALLOWED_STAGES,
    GeometryCorrectionError,
    GeometryDefect,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualityResult


@dataclass(frozen=True, slots=True)
class MandatoryVisualCheck:
    field: str
    requirement: str
    status: str = "REQUIRES_HUMAN_VERIFICATION"


@dataclass(frozen=True, slots=True)
class VisualCorrectionTriage:
    asset_id: str
    reference_id: int
    image_sha256: str
    quality_decision: str
    semantic_available: bool
    mandatory_checks: tuple[MandatoryVisualCheck, ...]
    advisory_violations: tuple[str, ...]
    observed_failure: str
    selected_field: str | None
    selected_defect: GeometryDefect | None
    stages: tuple[str, ...]
    gpu_execution_authorized: bool = False
    cap_registration_allowed: bool = False
    canon_approval_allowed: bool = False
    governed_attempt_allowed: bool = False

    @property
    def unresolved_mandatory_checks(self) -> int:
        return len(self.mandatory_checks)

    def describe(self) -> str:
        lines = [
            "F5.4.2 — Generalized Candidate Correction Triage (READ ONLY)",
            f"Asset: {self.asset_id} | Candidate: {self.reference_id}",
            f"Image SHA-256: {self.image_sha256}",
            f"Saved review decision: {self.quality_decision}",
            f"Mandatory checks requiring independent verification: {len(self.mandatory_checks)}",
            "",
            "REVIEWED DESIGN FIELDS (NOT AUTOMATICALLY PASSED)",
        ]
        for check in self.mandatory_checks:
            lines.append(f"{check.field}: {check.status} — {check.requirement}")
        lines.append("")
        lines.append("SEMANTIC FINDINGS (ADVISORY, NOT DESIGN AUTHORITY)")
        lines.extend(self.advisory_violations or ("No specific violations recorded.",))
        if self.selected_defect is not None:
            lines.extend(
                (
                    "",
                    f"OPERATOR SELECTED: {self.selected_defect.value}",
                    f"Accepted field: {self.selected_field}",
                    f"Observed failure: {self.observed_failure}",
                    f"Suggested stages: {' -> '.join(self.stages)}",
                )
            )
        lines.extend(
            (
                "",
                "Proposed masks require separate review and source binding.",
                "Any actual correction requires separate governed eligibility and consent.",
                "No API call, generation, CAP registration, Canon approval or attempt reservation.",
            )
        )
        return "\n".join(lines)


def candidate_visual_triage(
    report: CandidateQualityResult,
    *,
    selected_field: str | None = None,
    selected_defect: GeometryDefect | None = None,
    observed_failure: str = "",
) -> VisualCorrectionTriage:
    """Build a safe advisory from the reviewed CAP + a completed quality result."""
    snapshot = report.snapshot
    checks = tuple(
        MandatoryVisualCheck(field=field, requirement=requirement)
        for field, requirement in snapshot.accepted_fields
    )
    if not checks:
        raise GeometryCorrectionError("Candidate has no reviewed design checks")
    if (
        snapshot.reference_role != "supplementary"
        or snapshot.reference_status != "candidate"
        or len(snapshot.image_sha256) != 64
    ):
        raise GeometryCorrectionError("Candidate identity or review status invalid")
    if selected_field is None and selected_defect is None:
        if observed_failure.strip():
            raise GeometryCorrectionError("Unbound failure text is not a reviewed defect")
        stages: tuple[str, ...] = ()
    else:
        if not isinstance(selected_defect, GeometryDefect):
            raise GeometryCorrectionError("Select a supported visual defect type")
        if selected_field not in dict(snapshot.accepted_fields):
            raise GeometryCorrectionError("Correction must select one reviewed CAP field")
        if not 12 <= len(observed_failure.strip()) <= 2000:
            raise GeometryCorrectionError("Provide a specific observed failure (12-2000 chars)")
        stages = tuple(stage.value for stage in _ALLOWED_STAGES[selected_defect])
    violations = tuple(report.semantic.violations) if report.semantic is not None else ()
    return VisualCorrectionTriage(
        asset_id=snapshot.asset_id,
        reference_id=snapshot.reference_id,
        image_sha256=snapshot.image_sha256,
        quality_decision=report.decision,
        semantic_available=report.semantic is not None,
        mandatory_checks=checks,
        advisory_violations=violations,
        observed_failure=observed_failure.strip(),
        selected_field=selected_field,
        selected_defect=selected_defect,
        stages=stages,
    )
