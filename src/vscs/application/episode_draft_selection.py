"""Selection staging for governed, incremental Episode Draft timelines.

Missing shots remain coverage blockers, never fabricated ShotSelection objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vscs.application.assembly_contracts import (
    AssemblyScope,
    AssemblyScopeKind,
    AssemblyState,
    AssemblyTimelineRevision,
    ShotSelection,
)
from vscs.application.episode_shot_set_resolver import EpisodeShotSet


@dataclass(frozen=True, slots=True)
class DraftMediaChoice:
    shot_id: str
    media_id: str
    eligible: bool
    reason: str


def approved_media_choices(
    authority: EpisodeShotSet, records: tuple[Any, ...]
) -> tuple[DraftMediaChoice, ...]:
    """Expose only recorded approvals, not inferred or automatically assigned ones."""
    eligible_shots = set(authority.required_shot_ids)
    result: list[DraftMediaChoice] = []
    for record in records:
        shot_id = record.scope.shot_id
        if shot_id not in eligible_shots:
            continue
        approved = (
            getattr(record.kind, "value", "") == "video"
            and record.state.value == "approved"
            and any(event.to_state.value == "approved" for event in record.governance_history)
        )
        reason = "Human approval recorded" if approved else "Video approval/eligibility outstanding"
        if not record.file.checksum_sha256 or record.file.size_bytes is None:
            approved = False
            reason = "Media checksum or size evidence missing"
        result.append(DraftMediaChoice(shot_id, record.media_id, approved, reason))
    return tuple(sorted(result, key=lambda item: (item.shot_id, item.media_id)))


def build_partial_draft(
    authority: EpisodeShotSet,
    scope: AssemblyScope,
    assembly_id: str,
    revision_id: str,
    selected_media: tuple[tuple[str, Any, int, int, str], ...],
    *,
    frame_rate_num: int = 24,
    frame_rate_den: int = 1,
) -> AssemblyTimelineRevision:
    """Build a partial Draft using actual approved media and explicit frame ranges.

    Publication requires a separate real-media validator and append-only repository.
    This function never writes, approves, or declares completion.
    """
    if not authority.eligible:
        raise ValueError("Episode planning authority is not eligible")
    if scope.scope_kind is not AssemblyScopeKind.EPISODE or scope.scope_id != authority.episode_id:
        raise ValueError("Authoritative Episode scope does not match")
    ordered = {shot: index for index, shot in enumerate(authority.required_shot_ids)}
    if len({shot for shot, *_ in selected_media}) != len(selected_media):
        raise ValueError("Duplicate Shot selections")
    chosen = sorted(selected_media, key=lambda item: ordered.get(item[0], len(ordered)))
    selections: list[ShotSelection] = []
    for shot_id, record, first, last, approval_ref in chosen:
        if shot_id not in ordered or record.scope.shot_id != shot_id:
            raise ValueError("Media Shot identity does not match authoritative Shot")
        if (
            record.scope.episode_id != scope.scope_id
            or record.scope.production_id != scope.production_id
        ):
            raise ValueError("Media production or Episode identity mismatch")
        approved = record.state.value == "approved" and any(
            event.to_state.value == "approved" for event in record.governance_history
        )
        if (
            getattr(record.kind, "value", "") != "video"
            or not approved
            or not approval_ref.strip()
            or not record.file.checksum_sha256
            or record.file.size_bytes is None
        ):
            raise ValueError("Only real approved media with checksum evidence may be staged")
        if not record.scope.scene_id:
            raise ValueError("Scene identity evidence missing")
        selection = ShotSelection(
            scene_id=record.scope.scene_id,
            shot_id=shot_id,
            generated_media_id=record.media_id,
            media_revision=str(record.revision),
            file_checksum=record.file.checksum_sha256,
            approval_evidence_ref=approval_ref,
            source_in_frame=first,
            source_out_frame=last,
            sequence_index=len(selections),
            media_state=record.state.value,
        )
        selections.append(selection)
    return AssemblyTimelineRevision(
        assembly_id=assembly_id,
        revision_id=revision_id,
        scope=scope,
        selections=tuple(selections),
        frame_rate_num=frame_rate_num,
        frame_rate_den=frame_rate_den,
        state=AssemblyState.DRAFT,
    )


def publish_partial_draft(
    revision: AssemblyTimelineRevision, repository: Any, evidence_validator: Any
) -> Any:
    """Append only after validating real source media and bytes.

    Incomplete Episode coverage is permitted for Draft only, never as a closure.
    """
    if revision.state is not AssemblyState.DRAFT:
        raise ValueError("Only Draft assembly revisions may be initialized")
    if not revision.selections:
        raise ValueError("A Draft must include at least one verified media selection")
    validation = evidence_validator.validate(revision, final_use=True)
    if not validation.allowed:
        raise ValueError("Draft publication blocked: " + "; ".join(validation.blockers))
    return repository.create(revision)
