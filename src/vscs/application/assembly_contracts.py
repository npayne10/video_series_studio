"""Immutable, renderer-neutral episode assembly contracts (Phase 20.18.2.3.7.2).

No persistence, media copying, approvals or provider execution occurs here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import ClassVar


class AssemblyContractError(ValueError):
    """Invalid or unauthorised assembly data."""


class AssemblyState(StrEnum):
    DRAFT = "draft"
    PROVISIONAL_REVIEW = "provisional_review"
    PICTURE_LOCKED = "picture_locked"
    POST_PRODUCTION = "post_production"
    FINAL_QC_REQUIRED = "final_qc_required"
    APPROVED = "approved"
    MASTERED = "mastered"
    SUPERSEDED = "superseded"


class AssemblyScopeKind(StrEnum):
    EPISODE = "episode"
    STANDALONE_VIDEO = "standalone_video"


def _required(value: str, name: str) -> None:
    if not value or not value.strip():
        raise AssemblyContractError(f"{name} is required")


def _checksum(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


@dataclass(frozen=True, slots=True)
class AssemblyScope:
    production_id: str
    scope_kind: AssemblyScopeKind
    scope_id: str
    declared_shot_set_revision: str
    story_structure_fingerprint: str

    def __post_init__(self) -> None:
        for name in ("production_id", "scope_id", "declared_shot_set_revision"):
            _required(getattr(self, name), name)
        if not _checksum(self.story_structure_fingerprint):
            raise AssemblyContractError("story_structure_fingerprint must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class ShotSelection:
    scene_id: str
    shot_id: str
    generated_media_id: str
    media_revision: str
    file_checksum: str
    approval_evidence_ref: str | None
    source_in_frame: int
    source_out_frame: int
    sequence_index: int
    media_state: str
    boundary_evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("scene_id", "shot_id", "generated_media_id", "media_revision"):
            _required(getattr(self, name), name)
        if not _checksum(self.file_checksum):
            raise AssemblyContractError("file_checksum must be lowercase SHA-256")
        if self.source_in_frame < 0 or self.source_out_frame <= self.source_in_frame:
            raise AssemblyContractError("Shot frame range must be positive and half-open")
        if self.sequence_index < 0:
            raise AssemblyContractError("sequence_index must be nonnegative")
        if self.media_state not in {"generated", "under_review", "approved"}:
            raise AssemblyContractError("Unsupported assembly source media state")
        if self.media_state == "approved" and not self.approval_evidence_ref:
            raise AssemblyContractError("Approved source requires approval evidence")

    @property
    def frame_count(self) -> int:
        return self.source_out_frame - self.source_in_frame


@dataclass(frozen=True, slots=True)
class AssemblyTimelineRevision:
    assembly_id: str
    revision_id: str
    scope: AssemblyScope
    selections: tuple[ShotSelection, ...]
    frame_rate_num: int
    frame_rate_den: int
    state: AssemblyState = AssemblyState.DRAFT
    predecessor_revision: str | None = None
    reviewer_id: str | None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        _required(self.assembly_id, "assembly_id")
        _required(self.revision_id, "revision_id")
        if self.schema_version != "1.0":
            raise AssemblyContractError("Unsupported timeline schema_version")
        if self.frame_rate_num <= 0 or self.frame_rate_den <= 0:
            raise AssemblyContractError("Frame rate must be positive")
        if Fraction(self.frame_rate_num, self.frame_rate_den) <= 0:
            raise AssemblyContractError("Invalid frame rate")
        indexes = [item.sequence_index for item in self.selections]
        if indexes != list(range(len(indexes))):
            raise AssemblyContractError("Selections must have unique contiguous ordered indexes")
        if self.predecessor_revision == self.revision_id:
            raise AssemblyContractError("A revision cannot supersede itself")

    @property
    def total_frames(self) -> int:
        return sum(item.frame_count for item in self.selections)

    @property
    def duration_seconds(self) -> Fraction:
        return Fraction(self.total_frames * self.frame_rate_den, self.frame_rate_num)

    @property
    def fingerprint(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "assembly_id": self.assembly_id,
            "revision_id": self.revision_id,
            "scope": {
                "production_id": self.scope.production_id,
                "scope_kind": self.scope.scope_kind.value,
                "scope_id": self.scope.scope_id,
                "declared_shot_set_revision": self.scope.declared_shot_set_revision,
                "story_structure_fingerprint": self.scope.story_structure_fingerprint,
            },
            "selections": [
                {
                    "scene_id": item.scene_id,
                    "shot_id": item.shot_id,
                    "generated_media_id": item.generated_media_id,
                    "media_revision": item.media_revision,
                    "file_checksum": item.file_checksum,
                    "approval_evidence_ref": item.approval_evidence_ref,
                    "source_in_frame": item.source_in_frame,
                    "source_out_frame": item.source_out_frame,
                    "sequence_index": item.sequence_index,
                    "media_state": item.media_state,
                    "boundary_evidence_refs": list(item.boundary_evidence_refs),
                }
                for item in self.selections
            ],
            "frame_rate_num": self.frame_rate_num,
            "frame_rate_den": self.frame_rate_den,
            "state": self.state.value,
            "predecessor_revision": self.predecessor_revision,
            "reviewer_id": self.reviewer_id,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AssemblyValidation:
    allowed: bool
    blockers: tuple[str, ...]


class AssemblyGovernanceValidator:
    """Fail closed for approval and locking; never changes external state."""

    _transitions: ClassVar[dict[AssemblyState, frozenset[AssemblyState]]] = {
        AssemblyState.DRAFT: frozenset(
            {AssemblyState.PROVISIONAL_REVIEW, AssemblyState.SUPERSEDED}
        ),
        AssemblyState.PROVISIONAL_REVIEW: frozenset(
            {
                AssemblyState.PICTURE_LOCKED,
                AssemblyState.SUPERSEDED,
            }
        ),
        AssemblyState.PICTURE_LOCKED: frozenset(
            {AssemblyState.POST_PRODUCTION, AssemblyState.SUPERSEDED}
        ),
        AssemblyState.POST_PRODUCTION: frozenset(
            {
                AssemblyState.FINAL_QC_REQUIRED,
                AssemblyState.SUPERSEDED,
            }
        ),
        AssemblyState.FINAL_QC_REQUIRED: frozenset(
            {AssemblyState.APPROVED, AssemblyState.SUPERSEDED}
        ),
        AssemblyState.APPROVED: frozenset({AssemblyState.MASTERED, AssemblyState.SUPERSEDED}),
        AssemblyState.MASTERED: frozenset(),
        AssemblyState.SUPERSEDED: frozenset(),
    }

    def validate(
        self, revision: AssemblyTimelineRevision, *, final_use: bool
    ) -> AssemblyValidation:
        blockers: list[str] = []
        if not revision.selections:
            blockers.append("Assembly has no selected Shots")
        if final_use:
            for selection in revision.selections:
                if selection.media_state != "approved" or not selection.approval_evidence_ref:
                    blockers.append(f"{selection.shot_id}: source is not human-approved")
        return AssemblyValidation(not blockers, tuple(blockers))

    def transition(
        self,
        revision: AssemblyTimelineRevision,
        target: AssemblyState,
        *,
        human_approval_ref: str | None = None,
    ) -> AssemblyValidation:
        blockers: list[str] = []
        if target not in self._transitions[revision.state]:
            blockers.append(f"Invalid assembly transition: {revision.state} -> {target}")
        if target in {
            AssemblyState.PICTURE_LOCKED,
            AssemblyState.APPROVED,
            AssemblyState.MASTERED,
        }:
            blockers.extend(self.validate(revision, final_use=True).blockers)
            if not human_approval_ref or not human_approval_ref.strip():
                blockers.append("Explicit human approval evidence required")
        return AssemblyValidation(not blockers, tuple(blockers))
