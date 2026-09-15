"""UPD compiler composition that prepares governed references before compilation."""

from __future__ import annotations

from vscs.application.governed_reference_plan_source import (
    GovernedReferencePlanSource,
    PersistedGovernedReferencePlanSource,
)
from vscs.application.governed_reference_suitability import (
    GovernedReferenceSuitabilityError,
    GovernedReferenceSuitabilityService,
)
from vscs.application.production_package import ProductionPackageService
from vscs.application.projects import ProjectService
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerError,
    UniversalProductionDescriptionCompilerService,
    UniversalProductionDescriptionStatus,
)


class GovernedReferenceAwareUniversalProductionDescriptionCompilerService(
    UniversalProductionDescriptionCompilerService
):
    """Prepare explicit provider-ready reference authority before UPD transitions."""

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
        reference_plans: GovernedReferencePlanSource | None = None,
        preparer: GovernedReferenceSuitabilityService | None = None,
    ) -> None:
        store = reference_plans or PersistedGovernedReferencePlanSource(projects)
        super().__init__(projects, packages, reference_plans=store)
        self.reference_preparer = preparer or GovernedReferenceSuitabilityService(
            projects,
            store if isinstance(store, PersistedGovernedReferencePlanSource) else None,
        )

    def create_from_current_package(self, shot_id: str):
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            return super().create_from_current_package(normalized)
        package = self.packages.current_package(normalized) or self.packages.materialize(normalized)
        self._prepare_references(package)
        return super().create_from_current_package(normalized)

    def rebase_to_current_package(self, shot_id: str):
        current = self._require_draft(shot_id)
        if current.status is UniversalProductionDescriptionStatus.READY:
            return super().rebase_to_current_package(shot_id)
        package = self.packages.require_current_package(current.shot_id)
        self._prepare_references(package)
        return super().rebase_to_current_package(current.shot_id)

    def mark_ready(self, shot_id: str):
        current = self._require_draft(shot_id)
        if not self.is_current(current):
            return super().mark_ready(shot_id)
        package = self.packages.require_current_package(current.shot_id)
        self._prepare_references(package)
        return super().mark_ready(current.shot_id)

    def compile(self, shot_id: str):
        draft = self._require_draft(shot_id)
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            return super().compile(shot_id)
        package = self.packages.require_current_package(draft.shot_id)
        self._prepare_references(package)
        return super().compile(draft.shot_id)

    def _prepare_references(self, package) -> None:
        try:
            self.reference_preparer.ensure_for_package(package)
        except GovernedReferenceSuitabilityError as exc:
            raise UniversalProductionDescriptionCompilerError(
                f"Governed reference preparation failed: {exc}"
            ) from exc
