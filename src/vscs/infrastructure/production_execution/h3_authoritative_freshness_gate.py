"""Q3.1.3.4 read-only gate with caller-owned authoritative source retrieval.

The caller MUST supply a loader that retrieves the CURRENT approved task and
ProductionPackage from existing repositories. No source is written by this gate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilerService,
)
from vscs.application.production_execution.span_scoped_provider_inputs import (
    SpanScopedProviderInputCompiler,
)

from .h3_reference_selection_governance import H3ReferenceGovernanceError
from .h3_span_freshness_provenance import (
    H3SpanFreshnessReport,
    validate_h3_span_freshness,
)

if TYPE_CHECKING:
    from vscs.application.production_execution.package_compilation import CompiledProductionPackage
    from vscs.application.production_package import ProductionPackage
    from vscs.application.production_tasks import ProductionTask
    from vscs.application.provider_reference_capacity import ProviderReferenceCapacityProjection

    from .minimax_h3_span_adapter import MiniMaxH3SpanExecution

CurrentSourceLoader = Callable[[], tuple["ProductionTask", "ProductionPackage"]]


@dataclass(frozen=True)
class H3AuthoritativeFreshnessGateResult:
    report: H3SpanFreshnessReport
    refreshed_package_fingerprint: str
    verified_against_current_loader: bool = True
    advisory_only: bool = True


def verify_current_h3_reference_authority(
    *,
    reference_root: Path,
    load_current_source: CurrentSourceLoader,
    original: CompiledProductionPackage,
    execution: MiniMaxH3SpanExecution,
    projection: ProviderReferenceCapacityProjection,
    guide_overlap_ids: frozenset[str] = frozenset(),
) -> H3AuthoritativeFreshnessGateResult:
    """Recompile current approved source, then verify the exact execution span.

    The supplied loader must be backed by the caller's genuine current-authority
    repositories. This function cannot independently authenticate that loader.
    """
    if not reference_root.is_dir():
        raise H3ReferenceGovernanceError("Current source reference root does not exist")
    try:
        task, source = load_current_source()
        if task.shot_id != original.shot_id or source.shot_id != original.shot_id:
            raise H3ReferenceGovernanceError("Current source Shot identity changed")
        refreshed = ProductionPackageCompilerService(reference_root=reference_root).compile(
            task, source, profile=original.profile
        )
        span_plan = SpanScopedProviderInputCompiler().compile(refreshed)
    except H3ReferenceGovernanceError:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError, TypeError) as exc:
        raise H3ReferenceGovernanceError(
            "Current authority cannot be independently recompiled"
        ) from exc
    report = validate_h3_span_freshness(
        original,
        refreshed,
        span_plan,
        execution,
        projection,
        guide_overlap_ids=guide_overlap_ids,
    )
    return H3AuthoritativeFreshnessGateResult(
        report=report,
        refreshed_package_fingerprint=refreshed.package_fingerprint,
    )
