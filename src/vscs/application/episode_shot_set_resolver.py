"""Fail-closed Episode Shot-set resolution and assembly coverage (Checkpoint 4B).

This module does not grant episode closure authority or create media approvals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EpisodeShotSet:
    episode_id: str
    required_shot_ids: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return bool(self.required_shot_ids) and not self.blockers


@dataclass(frozen=True, slots=True)
class EpisodeCoverage:
    expected: tuple[str, ...]
    selected: tuple[str, ...]
    missing: tuple[str, ...]
    extra: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers


def resolve_episode_shots(
    episode_id: str,
    episodes: Any,
    scenes: Any,
    shots: Any,
    reviews: Any,
) -> EpisodeShotSet:
    """Resolve order from governed Episode → Scene → Shot and review authority."""
    normalized = episode_id.strip().upper()
    blockers: list[str] = []
    episode = episodes.plan(normalized)
    if episode is None or not episode.production_ready:
        blockers.append("Episode Plan is missing or not Ready")
    scene_plans = scenes.list_plans(episode_id=normalized)
    if not scene_plans:
        blockers.append("No governed Scene Plans for Episode")
    ordered: list[str] = []
    for scene in scene_plans:
        if not scenes.is_production_ready(scene):
            blockers.append(f"{scene.scene_id}: Scene Plan is not current and Ready")
        shot_plans = shots.list_plans(scene_id=scene.scene_id)
        if not shot_plans:
            blockers.append(f"{scene.scene_id}: No governed Shot Plans")
        for shot in shot_plans:
            ordered.append(shot.shot_id)
            if not shots.is_production_ready(shot):
                blockers.append(f"{shot.shot_id}: Shot Plan is not current and Ready")
            review = reviews.review(shot.shot_id)
            if review is None or not reviews.is_production_ready(review):
                blockers.append(f"{shot.shot_id}: Planning Review is not approved and current")
    if len(ordered) != len(set(ordered)):
        blockers.append("Duplicate Shot identifiers in Episode plan")
    return EpisodeShotSet(normalized, tuple(ordered), tuple(blockers))


def reconcile_episode_coverage(
    authority: EpisodeShotSet, selections: tuple[Any, ...]
) -> EpisodeCoverage:
    """Compare a governed Shot order to persisted selections; never infer media approval."""
    selected = tuple(item.shot_id for item in selections)
    missing = tuple(shot for shot in authority.required_shot_ids if shot not in selected)
    extra = tuple(shot for shot in selected if shot not in authority.required_shot_ids)
    blockers = list(authority.blockers)
    if not authority.eligible:
        blockers.append("Authoritative Episode Shot set is not eligible")
    if missing:
        blockers.append("Required Shots missing: " + ", ".join(missing))
    if extra:
        blockers.append("Unplanned Shots selected: " + ", ".join(extra))
    if selected != authority.required_shot_ids:
        blockers.append("Timeline Shot order differs from authoritative planning")
    if len(selected) != len(set(selected)):
        blockers.append("Duplicate timeline Shot selections")
    for item in selections:
        if item.media_state != "approved" or not item.approval_evidence_ref:
            blockers.append(f"{item.shot_id}: Generated Media approval evidence missing")
    return EpisodeCoverage(
        authority.required_shot_ids, selected, missing, extra, tuple(blockers)
    )


def initialize_governed_episode_timeline(
    authority: EpisodeShotSet,
    revision: Any,
    repository: Any,
    evidence_validator: Any,
) -> Any:
    """Publish an immutable draft only from complete approved existing media evidence.

    Caller supplies a fully formed revision; no fabricated media identifiers,
    approvals, or generated timeline selections are permitted.
    """
    from vscs.application.assembly_contracts import AssemblyScopeKind, AssemblyState

    if revision.scope.scope_kind is not AssemblyScopeKind.EPISODE:
        raise ValueError("Only governed Episode assembly is supported")
    if revision.scope.scope_id != authority.episode_id:
        raise ValueError("Episode authority and timeline scope differ")
    if revision.state is not AssemblyState.DRAFT:
        raise ValueError("Initialization requires a Draft assembly revision")
    coverage = reconcile_episode_coverage(authority, revision.selections)
    if not coverage.ready:
        raise ValueError("Timeline initialization blocked: " + "; ".join(coverage.blockers))
    validation = evidence_validator.validate(revision, final_use=True)
    if not validation.ready:
        raise ValueError("Timeline media evidence blocked: " + "; ".join(validation.blockers))
    return repository.create(revision)
