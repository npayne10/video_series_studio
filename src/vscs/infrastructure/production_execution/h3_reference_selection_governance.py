"""Q3.1.3 proposal-only H3 reference selection governance.

Does not compile, stage, mutate or submit production assets. A guide overlap is a
review recommendation, never automatic authority to discard a required reference.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

ReferenceKind = Literal["character", "environment", "visual_element", "other"]
Disposition = Literal["retain", "propose_defer", "blocked"]


class H3ReferenceGovernanceError(ValueError):
    """Unsafe reference selection request."""


@dataclass(frozen=True)
class H3ReferenceCandidate:
    reference_id: str
    kind: ReferenceKind
    required: bool
    guide_represents_asset: bool = False

    def __post_init__(self) -> None:
        if not self.reference_id.strip():
            raise H3ReferenceGovernanceError("Reference ID cannot be blank")
        if self.kind not in ("character", "environment", "visual_element", "other"):
            raise H3ReferenceGovernanceError("Unknown reference kind")


@dataclass(frozen=True)
class H3ReferenceDecision:
    reference_id: str
    disposition: Disposition
    reason: str


@dataclass(frozen=True)
class H3ReferenceProposal:
    decisions: tuple[H3ReferenceDecision, ...]
    capacity: int
    fingerprint: str
    requires_operator_review: bool = True

    @property
    def retained_ids(self) -> tuple[str, ...]:
        return tuple(d.reference_id for d in self.decisions if d.disposition == "retain")

    @property
    def proposed_deferred_ids(self) -> tuple[str, ...]:
        return tuple(d.reference_id for d in self.decisions if d.disposition == "propose_defer")


def propose_h3_reference_selection(
    candidates: tuple[H3ReferenceCandidate, ...],
    *,
    capacity: int = 5,
) -> H3ReferenceProposal:
    """Make deterministic, non-executable suggestions, preserving required inputs."""
    if capacity <= 0 or capacity > 5:
        raise H3ReferenceGovernanceError("H3 capacity must be between 1 and 5")
    ids = [candidate.reference_id for candidate in candidates]
    if len(set(ids)) != len(ids):
        raise H3ReferenceGovernanceError("Duplicate reference IDs")
    required_count = sum(candidate.required for candidate in candidates)
    if required_count > capacity:
        raise H3ReferenceGovernanceError(
            "Required references exceed provider capacity; explicit replanning required"
        )
    decisions: list[H3ReferenceDecision] = []
    optional_slots = capacity - required_count
    optional_retained = 0
    for candidate in candidates:
        if candidate.required:
            decision = H3ReferenceDecision(
                candidate.reference_id, "retain", "Required by supplied authority"
            )
        elif candidate.guide_represents_asset:
            decision = H3ReferenceDecision(
                candidate.reference_id,
                "propose_defer",
                "Guide appears to represent asset; operator must review equivalence",
            )
        elif optional_retained < optional_slots:
            decision = H3ReferenceDecision(
                candidate.reference_id, "retain", "Optional reference within provider capacity"
            )
            optional_retained += 1
        else:
            decision = H3ReferenceDecision(
                candidate.reference_id,
                "propose_defer",
                "Optional reference exceeds capacity; operator review required",
            )
        decisions.append(decision)
    payload = {
        "capacity": capacity,
        "candidates": [
            {
                "id": c.reference_id,
                "kind": c.kind,
                "required": c.required,
                "guide_represents_asset": c.guide_represents_asset,
            }
            for c in candidates
        ],
        "decisions": [
            {"id": d.reference_id, "disposition": d.disposition, "reason": d.reason}
            for d in decisions
        ],
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return H3ReferenceProposal(tuple(decisions), capacity, fingerprint)
