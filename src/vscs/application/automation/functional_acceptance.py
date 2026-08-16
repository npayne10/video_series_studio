"""Read-only integration and functional acceptance for Phase 19.5.13."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .contracts import AutomationProposal, AutomationProposalStatus, AutomationProposalType
from .service import AutomationProposalService


class AcceptanceState(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    key: str
    title: str
    state: AcceptanceState
    detail: str


@dataclass(frozen=True, slots=True)
class FunctionalAcceptanceReport:
    story_id: str
    source_revision: str
    criteria: tuple[AcceptanceCriterion, ...]

    @property
    def passed(self) -> int:
        return sum(item.state is AcceptanceState.PASS for item in self.criteria)

    @property
    def review_required(self) -> int:
        return sum(item.state is AcceptanceState.REVIEW for item in self.criteria)

    @property
    def failed(self) -> int:
        return sum(item.state is AcceptanceState.FAIL for item in self.criteria)

    @property
    def accepted(self) -> bool:
        return self.failed == 0 and self.review_required == 0


class FunctionalAcceptanceService:
    """Evaluate current Phase 19 proposal state without mutating production authority."""

    _STRUCTURAL_TYPES = (
        AutomationProposalType.EPISODE,
        AutomationProposalType.SCENE,
        AutomationProposalType.SHOT,
    )
    _SPECIALIST_TYPES = (
        AutomationProposalType.ACTION_PERFORMANCE,
        AutomationProposalType.ENVIRONMENT,
        AutomationProposalType.CAMERA,
        AutomationProposalType.LIGHTING,
        AutomationProposalType.CONTINUITY,
    )
    _NON_GLOBAL_SCOPES = frozenset({"prompt_element", "scene_continuity"})

    def __init__(self, proposals: AutomationProposalService) -> None:
        self._proposals = proposals

    def evaluate(self, *, story_id: str, source_revision: str) -> FunctionalAcceptanceReport:
        story = story_id.strip().upper()
        revision = source_revision.strip()
        if not story or not revision:
            raise ValueError("Story ID and source revision are required")
        current = tuple(
            proposal
            for proposal in self._proposals.list_proposals()
            if proposal.provenance.source_story_id == story
            and proposal.provenance.source_revision == revision
        )
        criteria = (
            self._proposal_set(current),
            self._structural_coverage(current),
            self._specialist_coverage(current),
            self._shot_specialist_coverage(current),
            self._provenance_integrity(current, story, revision),
            self._human_acceptance_integrity(current),
            self._canonical_governance(current),
            self._approval_boundary(current),
        )
        return FunctionalAcceptanceReport(story, revision, criteria)

    @staticmethod
    def _proposal_set(proposals: tuple[AutomationProposal, ...]) -> AcceptanceCriterion:
        if proposals:
            return AcceptanceCriterion(
                "proposal-set",
                "Current revision proposal set",
                AcceptanceState.PASS,
                f"{len(proposals)} proposal(s) belong to the current Story revision.",
            )
        return AcceptanceCriterion(
            "proposal-set",
            "Current revision proposal set",
            AcceptanceState.FAIL,
            "No Phase 19 automation proposals exist for the current Story revision.",
        )

    @classmethod
    def _structural_coverage(cls, proposals: tuple[AutomationProposal, ...]) -> AcceptanceCriterion:
        counts = {
            kind: sum(item.proposal_type is kind for item in proposals)
            for kind in cls._STRUCTURAL_TYPES
        }
        missing = [kind.value for kind, count in counts.items() if count == 0]
        detail = ", ".join(f"{kind.value}={counts[kind]}" for kind in cls._STRUCTURAL_TYPES)
        if missing:
            return AcceptanceCriterion(
                "structural-coverage",
                "Episode / Scene / Shot structural coverage",
                AcceptanceState.FAIL,
                f"Missing structural proposal types: {', '.join(missing)}. Current counts: {detail}.",
            )
        return AcceptanceCriterion(
            "structural-coverage",
            "Episode / Scene / Shot structural coverage",
            AcceptanceState.PASS,
            detail,
        )

    @classmethod
    def _specialist_coverage(cls, proposals: tuple[AutomationProposal, ...]) -> AcceptanceCriterion:
        counts = {
            kind: sum(item.proposal_type is kind for item in proposals)
            for kind in cls._SPECIALIST_TYPES
        }
        missing = [kind.value for kind, count in counts.items() if count == 0]
        detail = ", ".join(f"{kind.value}={counts[kind]}" for kind in cls._SPECIALIST_TYPES)
        if missing:
            return AcceptanceCriterion(
                "specialist-coverage",
                "Shot specialist proposal coverage",
                AcceptanceState.REVIEW,
                f"Missing specialist proposal types: {', '.join(missing)}. Current counts: {detail}.",
            )
        return AcceptanceCriterion(
            "specialist-coverage",
            "Shot specialist proposal coverage",
            AcceptanceState.PASS,
            detail,
        )

    @classmethod
    def _shot_specialist_coverage(
        cls, proposals: tuple[AutomationProposal, ...]
    ) -> AcceptanceCriterion:
        shot_ids = {
            item.target_id
            for item in proposals
            if item.proposal_type is AutomationProposalType.SHOT
        }
        if not shot_ids:
            return AcceptanceCriterion(
                "shot-specialist-coverage",
                "Every Shot has production specialist evidence",
                AcceptanceState.FAIL,
                "No Shot proposals exist for coverage evaluation.",
            )
        missing: list[str] = []
        for kind in cls._SPECIALIST_TYPES:
            targets = {item.target_id for item in proposals if item.proposal_type is kind}
            uncovered = sorted(shot_ids - targets)
            if uncovered:
                missing.append(f"{kind.value}: {len(uncovered)} uncovered")
        if missing:
            return AcceptanceCriterion(
                "shot-specialist-coverage",
                "Every Shot has production specialist evidence",
                AcceptanceState.REVIEW,
                "; ".join(missing),
            )
        return AcceptanceCriterion(
            "shot-specialist-coverage",
            "Every Shot has production specialist evidence",
            AcceptanceState.PASS,
            f"All {len(shot_ids)} Shot proposal(s) have action/performance, environment, camera, lighting and continuity evidence.",
        )

    @staticmethod
    def _provenance_integrity(
        proposals: tuple[AutomationProposal, ...], story_id: str, source_revision: str
    ) -> AcceptanceCriterion:
        stale = tuple(
            item
            for item in proposals
            if item.provenance.source_story_id != story_id
            or item.provenance.source_revision != source_revision
        )
        if stale:
            return AcceptanceCriterion(
                "provenance-integrity",
                "Story revision provenance integrity",
                AcceptanceState.FAIL,
                f"{len(stale)} proposal(s) carry stale or foreign provenance.",
            )
        return AcceptanceCriterion(
            "provenance-integrity",
            "Story revision provenance integrity",
            AcceptanceState.PASS,
            "Every evaluated proposal is tied to the requested Story and source revision.",
        )

    @staticmethod
    def _human_acceptance_integrity(
        proposals: tuple[AutomationProposal, ...],
    ) -> AcceptanceCriterion:
        invalid = tuple(
            item
            for item in proposals
            if (item.status is AutomationProposalStatus.ACCEPTED and not item.accepted_by.strip())
            or (item.status is AutomationProposalStatus.REJECTED and not item.rejected_by.strip())
        )
        if invalid:
            return AcceptanceCriterion(
                "human-acceptance-integrity",
                "Human proposal-governance integrity",
                AcceptanceState.FAIL,
                f"{len(invalid)} accepted/rejected proposal(s) lack explicit human identity.",
            )
        return AcceptanceCriterion(
            "human-acceptance-integrity",
            "Human proposal-governance integrity",
            AcceptanceState.PASS,
            "Accepted and rejected proposals retain explicit human governance identity.",
        )

    @classmethod
    def _canonical_governance(
        cls, proposals: tuple[AutomationProposal, ...]
    ) -> AcceptanceCriterion:
        assets = tuple(
            item for item in proposals if item.proposal_type is AutomationProposalType.ASSET
        )
        if not assets:
            return AcceptanceCriterion(
                "canonical-governance",
                "Canonical asset scope and identity governance",
                AcceptanceState.REVIEW,
                "No canonical entity-resolution proposals are present.",
            )
        blockers = []
        for item in assets:
            payload = item.payload
            scope = str(payload.get("canonical_scope", ""))
            resolved = bool(
                payload.get("resolution_kind") == "existing_canonical_asset"
                and payload.get("matched_asset_id")
            )
            if not resolved and scope not in cls._NON_GLOBAL_SCOPES:
                blockers.append(str(payload.get("name", item.target_id)))
        if blockers:
            preview = ", ".join(blockers[:5])
            suffix = "" if len(blockers) <= 5 else f" and {len(blockers) - 5} more"
            return AcceptanceCriterion(
                "canonical-governance",
                "Canonical asset scope and identity governance",
                AcceptanceState.REVIEW,
                f"{len(blockers)} global-canonical decision(s) remain unresolved: {preview}{suffix}.",
            )
        return AcceptanceCriterion(
            "canonical-governance",
            "Canonical asset scope and identity governance",
            AcceptanceState.PASS,
            "Every detected entity is either canonically resolved or explicitly scoped outside global XPD authority.",
        )

    @staticmethod
    def _approval_boundary(proposals: tuple[AutomationProposal, ...]) -> AcceptanceCriterion:
        fabricated = tuple(
            item
            for item in proposals
            if bool(item.payload.get("production_approved"))
            or str(item.payload.get("approval_status", "")).casefold() == "approved"
        )
        if fabricated:
            return AcceptanceCriterion(
                "approval-boundary",
                "Automation never fabricates final Production Approval",
                AcceptanceState.FAIL,
                f"{len(fabricated)} proposal(s) contain final approval markers.",
            )
        return AcceptanceCriterion(
            "approval-boundary",
            "Automation never fabricates final Production Approval",
            AcceptanceState.PASS,
            "No automation proposal contains a final Production Approval marker.",
        )
