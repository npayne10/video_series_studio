"""Read-only review, gap detection and repair suggestions for Phase 19.5.11."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .contracts import AutomationProposalStatus, AutomationProposalType
from .service import AutomationProposalService


class ReviewGapSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


@dataclass(frozen=True, slots=True)
class ReviewGap:
    gap_id: str
    severity: ReviewGapSeverity
    category: str
    target_id: str
    summary: str
    evidence: str
    repair_suggestion: str
    proposal_id: str = ""


@dataclass(frozen=True, slots=True)
class ProposalReviewReport:
    story_id: str
    source_revision: str
    proposal_count: int
    gaps: tuple[ReviewGap, ...]

    @property
    def blocker_count(self) -> int:
        return sum(gap.severity is ReviewGapSeverity.BLOCKER for gap in self.gaps)

    @property
    def warning_count(self) -> int:
        return sum(gap.severity is ReviewGapSeverity.WARNING for gap in self.gaps)


class ProposalReviewGapDetectionService:
    """Detect production gaps without accepting, repairing or mutating authority."""

    SPECIALIST_TYPES = (
        AutomationProposalType.ACTION_PERFORMANCE,
        AutomationProposalType.ENVIRONMENT,
        AutomationProposalType.CAMERA,
        AutomationProposalType.LIGHTING,
        AutomationProposalType.CONTINUITY,
    )

    def __init__(self, proposals: AutomationProposalService) -> None:
        self.proposals = proposals

    def review(self, *, story_id: str, source_revision: str) -> ProposalReviewReport:
        normalized_story = story_id.strip().upper()
        revision = source_revision.strip()
        current = tuple(
            item
            for item in self.proposals.list_proposals()
            if item.provenance.source_story_id == normalized_story
            and item.provenance.source_revision == revision
        )
        gaps: list[ReviewGap] = []
        shots = tuple(item for item in current if item.proposal_type is AutomationProposalType.SHOT)
        by_type_target = {(item.proposal_type, item.target_id): item for item in current}

        for asset in (
            item for item in current if item.proposal_type is AutomationProposalType.ASSET
        ):
            if str(asset.payload.get("canonical_status", "")) != "resolved":
                gaps.append(
                    ReviewGap(
                        gap_id=f"asset:{asset.proposal_id}",
                        severity=ReviewGapSeverity.BLOCKER,
                        category="canonical_asset",
                        target_id=asset.target_id,
                        proposal_id=asset.proposal_id,
                        summary="Canonical asset identity is unresolved.",
                        evidence=str(
                            asset.payload.get(
                                "resolution_note", "No fully resolved canonical asset."
                            )
                        ),
                        repair_suggestion=(
                            "Resolve this entity against existing XPD/CAP/Master Reference authority or "
                            "complete human canonical creation/review. Do not invent or auto-approve an asset."
                        ),
                    )
                )

        for shot in shots:
            for proposal_type in self.SPECIALIST_TYPES:
                specialist = by_type_target.get((proposal_type, shot.target_id))
                if specialist is None:
                    gaps.append(
                        ReviewGap(
                            gap_id=f"missing:{proposal_type.value}:{shot.target_id}",
                            severity=ReviewGapSeverity.BLOCKER,
                            category="missing_specialist_proposal",
                            target_id=shot.target_id,
                            summary=f"{proposal_type.value.replace('_', ' ').title()} proposal is missing.",
                            evidence=f"Accepted/current Shot {shot.target_id} has no matching proposal.",
                            repair_suggestion=(
                                f"Regenerate the {proposal_type.value.replace('_', ' ')} proposal for this "
                                "Shot from current upstream authority, then submit it to human review."
                            ),
                        )
                    )
                    continue
                if specialist.status is AutomationProposalStatus.REJECTED:
                    gaps.append(
                        ReviewGap(
                            gap_id=f"rejected:{specialist.proposal_id}",
                            severity=ReviewGapSeverity.WARNING,
                            category="rejected_proposal",
                            target_id=shot.target_id,
                            proposal_id=specialist.proposal_id,
                            summary=f"{proposal_type.value.replace('_', ' ').title()} proposal was rejected.",
                            evidence=specialist.review_notes
                            or "Human reviewer rejected this proposal.",
                            repair_suggestion=(
                                "Generate a replacement proposal from current upstream authority. Preserve the "
                                "human rejection record; do not automatically reverse it."
                            ),
                        )
                    )

        for continuity in (
            item for item in current if item.proposal_type is AutomationProposalType.CONTINUITY
        ):
            conflicts = continuity.payload.get("continuity_conflicts", ())
            if isinstance(conflicts, (list, tuple)) and conflicts:
                gaps.append(
                    ReviewGap(
                        gap_id=f"continuity:{continuity.proposal_id}",
                        severity=ReviewGapSeverity.BLOCKER,
                        category="continuity_conflict",
                        target_id=continuity.target_id,
                        proposal_id=continuity.proposal_id,
                        summary="Continuity conflict requires human resolution.",
                        evidence="; ".join(str(item) for item in conflicts),
                        repair_suggestion=(
                            "Review adjacent Shot states and correct the appropriate upstream proposal or governed "
                            "plan. Do not let automation choose which continuity state is canonical."
                        ),
                    )
                )

        gaps.sort(
            key=lambda item: (item.severity.value, item.category, item.target_id, item.gap_id)
        )
        return ProposalReviewReport(
            story_id=normalized_story,
            source_revision=revision,
            proposal_count=len(current),
            gaps=tuple(gaps),
        )
