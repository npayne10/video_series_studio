"""Q3.1.3.5 read-only adapter for persisted VSCS task/package authority."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .h3_authoritative_freshness_gate import (
    H3AuthoritativeFreshnessGateResult,
    verify_current_h3_reference_authority,
)
from .h3_reference_selection_governance import H3ReferenceGovernanceError

if TYPE_CHECKING:
    from vscs.application.production_execution.package_compilation import CompiledProductionPackage
    from vscs.application.production_package import ProductionPackage, ProductionPackageService
    from vscs.application.production_tasks.models import ProductionTask
    from vscs.application.production_tasks.repository import ProductionTaskRepository
    from vscs.application.provider_reference_capacity import ProviderReferenceCapacityProjection

    from .minimax_h3_span_adapter import MiniMaxH3SpanExecution


@dataclass(frozen=True)
class H3PersistedAuthoritySource:
    """Read current records by stable IDs without calling repository save methods."""

    tasks: ProductionTaskRepository
    packages: ProductionPackageService
    task_id: str
    source_package_id: str
    shot_id: str

    def load_current(self) -> tuple[ProductionTask, ProductionPackage]:
        task = self.tasks.get(self.task_id)
        if task is None:
            raise H3ReferenceGovernanceError("Authoritative ProductionTask is missing")
        if task.task_id != self.task_id or task.shot_id != self.shot_id:
            raise H3ReferenceGovernanceError("ProductionTask identity has changed")
        sources = self.packages.list_packages(shot_id=self.shot_id)
        matches = tuple(
            package for package in sources if package.package_id == self.source_package_id
        )
        if len(matches) != 1:
            raise H3ReferenceGovernanceError(
                "Expected exactly one persisted source ProductionPackage"
            )
        source = matches[0]
        if source.shot_id != self.shot_id:
            raise H3ReferenceGovernanceError("Persisted ProductionPackage Shot has changed")
        try:
            current = self.packages.current_package(self.shot_id)
        except Exception as exc:
            raise H3ReferenceGovernanceError(
                "Unable to verify current ProductionPackage planning authority"
            ) from exc
        if current is None:
            raise H3ReferenceGovernanceError("Current ProductionPackage authority is missing")
        if (
            current.package_id != source.package_id
            or current.shot_id != source.shot_id
            or current.source_fingerprint != source.source_fingerprint
            or current.package_fingerprint != source.package_fingerprint
        ):
            raise H3ReferenceGovernanceError(
                "Persisted ProductionPackage is not the current planning authority"
            )
        return task, source


def verify_persisted_h3_reference_authority(
    *,
    reference_root: Path,
    tasks: ProductionTaskRepository,
    packages: ProductionPackageService,
    original: CompiledProductionPackage,
    execution: MiniMaxH3SpanExecution,
    projection: ProviderReferenceCapacityProjection,
    guide_overlap_ids: frozenset[str] = frozenset(),
) -> H3AuthoritativeFreshnessGateResult:
    """Run the freshness gate against repository reads, never generated output."""
    loader = H3PersistedAuthoritySource(
        tasks=tasks,
        packages=packages,
        task_id=original.task_id,
        source_package_id=original.source_package_id,
        shot_id=original.shot_id,
    )
    return verify_current_h3_reference_authority(
        reference_root=reference_root,
        load_current_source=loader.load_current,
        original=original,
        execution=execution,
        projection=projection,
        guide_overlap_ids=guide_overlap_ids,
    )
