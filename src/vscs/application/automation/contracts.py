"""Provider-neutral proposal and provenance contracts for Phase 19.5 automation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class AutomationSourceKind(StrEnum):
    """Origin of one proposed production decision."""

    STORY = "story"
    AI_INFERENCE = "ai_inference"
    DETERMINISTIC_RESOLUTION = "deterministic_resolution"
    MANUAL = "manual"


class AutomationProposalType(StrEnum):
    """Authoritative planning boundary targeted by a proposal."""

    EPISODE = "episode"
    SCENE = "scene"
    SHOT = "shot"
    ASSET = "asset"
    ACTION_PERFORMANCE = "action_performance"
    ENVIRONMENT = "environment"
    CAMERA = "camera"
    LIGHTING = "lighting"
    CONTINUITY = "continuity"
    STYLE = "style"


class AutomationProposalStatus(StrEnum):
    """Human-governed lifecycle for automation proposals.

    No status in this lifecycle is production approval. Acceptance authorizes a
    later governed planner to consume the proposal; it never marks authority
    Ready or Approved.
    """

    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class AutomationProvenance:
    """Trace one proposal back to story authority and any semantic inference."""

    source_kind: AutomationSourceKind
    source_story_id: str
    source_revision: str
    source_scope: str
    provider: str = ""
    model: str = ""
    confidence: float = 1.0
    inference_note: str = ""
    resolution_method: str = ""
    generated_at: str = ""
    proposal_version: int = 1

    def __post_init__(self) -> None:
        if not self.source_story_id.strip():
            raise ValueError("Automation provenance requires a source Story ID")
        if not self.source_revision.strip():
            raise ValueError("Automation provenance requires a source revision")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Automation provenance confidence must be between 0 and 1")
        if self.proposal_version < 1:
            raise ValueError("Automation proposal version must be at least 1")
        if self.source_kind is AutomationSourceKind.AI_INFERENCE:
            if not self.provider.strip() or not self.model.strip():
                raise ValueError("AI provenance requires provider and model identity")


@dataclass(frozen=True, slots=True)
class AutomationProposal:
    """Reviewable production proposal that cannot itself become authority."""

    proposal_id: str
    proposal_type: AutomationProposalType
    target_id: str
    payload: dict[str, Any]
    provenance: AutomationProvenance
    status: AutomationProposalStatus = AutomationProposalStatus.PROPOSED
    review_notes: str = ""
    reviewed_by: str = ""
    accepted_by: str = ""
    rejected_by: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def human_reviewed(self) -> bool:
        return bool(self.reviewed_by.strip())

    @property
    def consumable(self) -> bool:
        """Return whether a governed planner may explicitly consume the proposal."""
        return self.status is AutomationProposalStatus.ACCEPTED and bool(self.accepted_by.strip())


class SemanticProductionProvider(Protocol):
    """Provider-neutral semantic interpretation boundary.

    Implementations return proposals only. They have no approval or governed
    planner mutation capability.
    """

    provider_name: str
    model_name: str

    def propose(
        self,
        *,
        story_id: str,
        source_revision: str,
        source_text: str,
        proposal_type: AutomationProposalType,
        target_id: str,
    ) -> AutomationProposal: ...


class TemplateSemanticProductionProvider:
    """Deterministic offline provider used for tests and future pipeline wiring."""

    provider_name = "vscs-template"
    model_name = "deterministic"

    def propose(
        self,
        *,
        story_id: str,
        source_revision: str,
        source_text: str,
        proposal_type: AutomationProposalType,
        target_id: str,
    ) -> AutomationProposal:
        import hashlib

        normalized_target = target_id.strip().upper()
        seed = (
            f"{story_id}|{source_revision}|{proposal_type.value}|{normalized_target}|{source_text}"
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return AutomationProposal(
            proposal_id=f"AUT-{proposal_type.value.upper()}-{digest[:12].upper()}",
            proposal_type=proposal_type,
            target_id=normalized_target,
            payload={"source_text": source_text.strip()},
            provenance=AutomationProvenance(
                source_kind=AutomationSourceKind.STORY,
                source_story_id=story_id.strip().upper(),
                source_revision=source_revision.strip(),
                source_scope="supplied source text",
                provider=self.provider_name,
                model=self.model_name,
                confidence=1.0,
                resolution_method="deterministic template proposal",
            ),
        )
