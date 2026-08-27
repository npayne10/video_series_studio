"""Application service for resolving and attaching governed reference plans."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .models import ClipProductionPackage
from .reference_roles import (
    ProviderReadyReferenceResolver,
    ProviderReferenceCapabilities,
    ReferenceResolutionResult,
    ReferenceRoleRequest,
    ReferenceTarget,
    ShotReference,
)


@dataclass(frozen=True, slots=True)
class ReferencePlanApplicationResult:
    """Resolved package and diagnostics for one reference-planning operation."""

    package: ClipProductionPackage
    resolution: ReferenceResolutionResult

    @property
    def passed(self) -> bool:
        """Return whether reference resolution is safe for provider execution."""
        return self.resolution.passed


class ReferencePlanApplicationService:
    """Resolve provider-ready references against a clip's render profile."""

    def __init__(self, resolver: ProviderReadyReferenceResolver) -> None:
        self.resolver = resolver

    def resolve_package(
        self,
        package: ClipProductionPackage,
        *,
        profile_id: str,
        requests: tuple[ReferenceRoleRequest, ...],
        provider_id: str | None = None,
        supplied_references: tuple[ShotReference, ...] = (),
        capabilities: ProviderReferenceCapabilities | None = None,
    ) -> ReferencePlanApplicationResult:
        """Resolve a governed plan and attach it to a copy of the package."""
        target = ReferenceTarget(
            width=package.render.width,
            height=package.render.height,
            profile_id=profile_id,
            provider_id=provider_id,
        )
        resolution = self.resolver.resolve(
            target=target,
            requests=requests,
            supplied_references=supplied_references,
            capabilities=capabilities,
        )
        metadata = dict(package.metadata)
        metadata["reference_plan.status"] = "resolved" if resolution.passed else "failed"
        metadata["reference_plan.reference_count"] = str(len(resolution.plan.references))
        resolved_package = replace(
            package,
            reference_plan=resolution.plan,
            metadata=metadata,
        )
        return ReferencePlanApplicationResult(
            package=resolved_package,
            resolution=resolution,
        )
