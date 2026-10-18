"""Governed immutable Assembly Timeline successor revisions (Phase 20.18.2.3.7.4).

No media, task, Shot or Episode approval states are changed by this service.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from vscs.application.assembly_contracts import (
    AssemblyState,
    AssemblyTimelineRevision,
    ShotSelection,
)
from vscs.application.episode_shot_set_resolver import EpisodeShotSet


def prepare_successor_revision(
    predecessor: AssemblyTimelineRevision,
    *,
    revision_id: str,
    authority: EpisodeShotSet,
    additions: tuple[ShotSelection, ...] = (),
    replacements: tuple[ShotSelection, ...] = (),
    replacement_reason: str | None = None,
) -> AssemblyTimelineRevision:
    """Preserve predecessor Shots and build an ordered Draft candidate.

    Additions cannot silently replace media. Replacements require explicit
    operator justification, and every selection retains approval evidence.
    """
    if predecessor.state is not AssemblyState.DRAFT:
        raise ValueError("Only Draft timeline revisions may be extended")
    if predecessor.scope.scope_id != authority.episode_id:
        raise ValueError("Predecessor Episode and authoritative Shot set differ")
    if not authority.required_shot_ids:
        raise ValueError("Authoritative Shot set is empty")
    if not revision_id.strip() or revision_id == predecessor.revision_id:
        raise ValueError("Successor must have a new revision identity")
    ordered = {shot: index for index, shot in enumerate(authority.required_shot_ids)}
    carried = {shot.shot_id: shot for shot in predecessor.selections}
    if len(carried) != len(predecessor.selections):
        raise ValueError("Duplicate predecessor Shot selections")
    new_shots = [item.shot_id for item in (*additions, *replacements)]
    if len(new_shots) != len(set(new_shots)):
        raise ValueError("Duplicate proposed Shot changes")
    for item in additions:
        if item.shot_id in carried:
            raise ValueError(f"{item.shot_id}: already selected; use governed replacement")
    if replacements and not replacement_reason:
        raise ValueError("Governed replacement justification is required")
    for item in replacements:
        if item.shot_id not in carried:
            raise ValueError(f"{item.shot_id}: not present; use governed addition")
    for item in (*additions, *replacements):
        if item.shot_id not in ordered:
            raise ValueError(f"{item.shot_id}: not in authoritative Episode")
        if any(blocker.startswith(f"{item.shot_id}:") for blocker in authority.blockers):
            raise ValueError(f"{item.shot_id}: planning approval is not current")
        if item.media_state != "approved" or not item.approval_evidence_ref:
            raise ValueError(f"{item.shot_id}: human-approved media evidence required")
    carried.update({item.shot_id: item for item in (*additions, *replacements)})
    if any(shot not in ordered for shot in carried):
        raise ValueError("Predecessor includes Shots outside current Episode authority")
    selections = tuple(
        replace(carried[shot], sequence_index=index)
        for index, shot in enumerate(sorted(carried, key=ordered.__getitem__))
    )
    return AssemblyTimelineRevision(
        assembly_id=predecessor.assembly_id,
        revision_id=revision_id,
        scope=predecessor.scope,
        selections=selections,
        frame_rate_num=predecessor.frame_rate_num,
        frame_rate_den=predecessor.frame_rate_den,
        state=AssemblyState.DRAFT,
        predecessor_revision=predecessor.revision_id,
    )


def publish_successor_revision(
    candidate: AssemblyTimelineRevision,
    *,
    repository: Any,
    validator: Any,
    authority: EpisodeShotSet,
    expected_predecessor_fingerprint: str,
    replacement_reason: str | None = None,
) -> Any:
    """Re-read exact predecessor, reject stale lineage, and verify media bytes.

    Append-only publication is delegated to the established repository.
    """
    if not candidate.predecessor_revision:
        raise ValueError("Successor revision requires a predecessor")
    predecessor = repository.get(candidate.assembly_id, candidate.predecessor_revision)
    if predecessor is None or predecessor.fingerprint != expected_predecessor_fingerprint:
        raise ValueError("Predecessor is missing or has changed")
    if candidate.state is not AssemblyState.DRAFT:
        raise ValueError("Only Draft successors may be published")
    if candidate.scope != predecessor.scope:
        raise ValueError("Successor cannot change authoritative Assembly Scope")
    if candidate.assembly_id != predecessor.assembly_id:
        raise ValueError("Successor Assembly identity differs")
    if candidate.revision_id == predecessor.revision_id:
        raise ValueError("Successor cannot overwrite predecessor")
    if authority.episode_id != candidate.scope.scope_id:
        raise ValueError("Current Episode authority differs")
    expected_order = tuple(
        shot
        for shot in authority.required_shot_ids
        if shot in {selection.shot_id for selection in candidate.selections}
    )
    if tuple(item.shot_id for item in candidate.selections) != expected_order:
        raise ValueError("Successor has missing, duplicate or out-of-order Shot selections")
    existing = {item.shot_id: item for item in predecessor.selections}
    proposed = {item.shot_id: item for item in candidate.selections}
    if len(proposed) != len(candidate.selections) or not set(existing).issubset(proposed):
        raise ValueError("Successor may not drop or duplicate predecessor Shots")
    changed = tuple(
        item.shot_id
        for item in candidate.selections
        if item.shot_id in existing
        and item != replace(existing[item.shot_id], sequence_index=item.sequence_index)
    )
    if changed and not (replacement_reason and replacement_reason.strip()):
        raise ValueError("Changed predecessor Shots require replacement justification")
    if not changed and len(proposed) == len(existing):
        raise ValueError("Successor contains no additions or governed replacements")
    for item in candidate.selections:
        if item.media_state != "approved" or not item.approval_evidence_ref:
            raise ValueError(f"{item.shot_id}: approval evidence missing")
        if any(blocker.startswith(f"{item.shot_id}:") for blocker in authority.blockers):
            raise ValueError(f"{item.shot_id}: planning or review is no longer current")
    validation = validator.validate(candidate, final_use=True)
    if not validation.allowed:
        raise ValueError("Successor media evidence blocked: " + "; ".join(validation.blockers))
    return repository.create(candidate)
