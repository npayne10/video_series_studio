"""Offline, evidence-bound relationship and geometry proposals; no invented dimensions."""

from __future__ import annotations

from dataclasses import dataclass
from vscs.application.caps.spatial_graph import SpatialSpecificationLookup

from vscs.application.caps.service import CAPNotFoundError
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)


@dataclass(frozen=True)
class SpatialProposal:
    asset_id: str
    relation: DependencyRelation
    evidence: str
    geometry_available: bool


@dataclass(frozen=True)
class SpatialProposalPlan:
    parent_asset_id: str
    proposed: tuple[SpatialProposal, ...]
    unresolved: tuple[str, ...]
    source: str = "Existing operator-reviewed CAP metadata; no model inference"


def propose_spatial_relationships(
    parent: CAPStructuredSpecification,
    candidates: tuple[CAPStructuredSpecification, ...],
) -> SpatialProposalPlan:
    """Suggest only documented inverse relationships, never imagined placements.

    A child that explicitly declares `located_in` parent may be proposed as
    `contains` on the parent. Suggestions are read-only until reviewed.
    """
    declared = {item.target_asset_id for item in parent.dependency_constraints}
    proposed: list[SpatialProposal] = []
    unresolved: list[str] = []
    for child in sorted(candidates, key=lambda item: item.asset_id):
        if child.asset_id == parent.asset_id or child.asset_id in declared:
            continue
        reverse = any(
            item.target_asset_id == parent.asset_id
            and item.relation is DependencyRelation.LOCATED_IN
            for item in child.dependency_constraints
        )
        if reverse:
            proposed.append(
                SpatialProposal(
                    asset_id=child.asset_id,
                    relation=DependencyRelation.CONTAINS,
                    evidence=f"{child.asset_id}: explicit located_in {parent.asset_id}",
                    geometry_available=child.geometry is not None,
                )
            )
    if parent.geometry is None:
        unresolved.append(
            "Parent geometry missing: dimensions and frame require operator evidence"
        )
    for item in parent.dependency_constraints:
        child = next(
            (candidate for candidate in candidates if candidate.asset_id == item.target_asset_id),
            None,
        )
        if child is None or child.geometry is None:
            unresolved.append(f"{item.target_asset_id}: typed geometry unavailable")
        if item.relation is DependencyRelation.CONTAINS and item.placement is None:
            unresolved.append(f"{item.target_asset_id}: no anchor placement declared")
    for item in proposed:
        if not item.geometry_available:
            unresolved.append(f"{item.asset_id}: proposed child has no typed geometry")
        unresolved.append(f"{item.asset_id}: placement/clearance not inferred")
    return SpatialProposalPlan(parent.asset_id, tuple(proposed), tuple(dict.fromkeys(unresolved)))


def load_project_spatial_candidates(
    specifications: SpatialSpecificationLookup, asset_ids: tuple[str, ...]
) -> tuple[CAPStructuredSpecification, ...]:
    """Read Draft CAP specs; missing/unavailable CAP records are skipped."""
    result: list[CAPStructuredSpecification] = []
    for asset_id in dict.fromkeys(asset_ids):
        try:
            spec = specifications.get(asset_id)
        except CAPNotFoundError:
            continue
        if spec is not None:
            result.append(spec)
    return tuple(result)


def reviewed_constraints(plan: SpatialProposalPlan) -> tuple[DependencyConstraint, ...]:
    """Construct minimal constraints only; caller must explicitly review/apply."""
    return tuple(
        DependencyConstraint(target_asset_id=item.asset_id, relation=item.relation)
        for item in plan.proposed
    )
