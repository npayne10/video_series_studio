"""UPD compiler composition that prepares governed references before compilation."""

from __future__ import annotations

import json

from vscs.application.governed_reference_plan_source import (
    GovernedReferencePlanSource,
    PersistedGovernedReferencePlanSource,
)
from vscs.application.governed_reference_suitability import (
    GovernedReferenceSuitabilityError,
    GovernedReferenceSuitabilityService,
)
from vscs.application.production_package import ProductionPackage, ProductionPackageService
from vscs.application.projects import ProjectService
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerError,
    UniversalProductionDescriptionCompilerService,
    UniversalProductionDescriptionDraft,
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

    def create_from_current_package(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            return super().create_from_current_package(normalized)
        package = self.packages.current_package(normalized) or self.packages.materialize(normalized)
        self._prepare_references(package)
        return super().create_from_current_package(normalized)

    def rebase_to_current_package(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        current = self._require_draft(shot_id)
        if current.status is UniversalProductionDescriptionStatus.READY:
            return super().rebase_to_current_package(shot_id)
        package = self.packages.require_current_package(current.shot_id)
        self._prepare_references(package)
        return super().rebase_to_current_package(current.shot_id)

    def mark_ready(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        current = self._require_draft(shot_id)
        if not self.is_current(current):
            return super().mark_ready(shot_id)
        package = self.packages.require_current_package(current.shot_id)
        self._prepare_references(package)
        return super().mark_ready(current.shot_id)

    def compile(self, shot_id: str) -> ProductionPackage:
        draft = self._require_draft(shot_id)
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            return super().compile(shot_id)
        package = self.packages.require_current_package(draft.shot_id)
        self._prepare_references(package)
        return super().compile(draft.shot_id)

    def _prepare_references(self, package: ProductionPackage) -> None:
        try:
            self._require_explicit_visual_coverage(package)
            self.reference_preparer.ensure_for_package(package)
        except GovernedReferenceSuitabilityError as exc:
            raise UniversalProductionDescriptionCompilerError(
                f"Governed reference preparation failed: {exc}"
            ) from exc

    def _require_explicit_visual_coverage(self, package: ProductionPackage) -> None:
        path = self.reference_preparer.suitability_file(package.shot_id)
        if not path.is_file():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        references = raw.get("references")
        if not isinstance(references, list):
            return

        required = self._required_visual_asset_ids(package)
        if not required:
            return
        covered: set[str] = set()
        for item in references:
            if not isinstance(item, dict):
                continue
            direct = self._normalized_asset_id(item.get("asset_id"))
            if direct:
                covered.add(direct)
            for key in ("contains_subjects", "contains_props", "contains_environments"):
                values = item.get(key)
                if not isinstance(values, list | tuple):
                    continue
                covered.update(
                    normalized
                    for value in values
                    if (normalized := self._normalized_asset_id(value))
                )

        missing = sorted(required - covered)
        if missing:
            raise GovernedReferenceSuitabilityError(
                f"Explicit suitability review for {package.shot_id} does not cover governed "
                "visual assets: "
                + ", ".join(missing)
                + ". Add explicit provider-ready references or a governed composition/group "
                "reference whose contains_* coverage names those asset IDs."
            )
        self._require_character_role_alignment(package, references)

    @classmethod
    def _required_visual_asset_ids(cls, package: ProductionPackage) -> set[str]:
        required = {
            normalized
            for reference in package.references
            if (normalized := cls._normalized_asset_id(reference.get("asset_id")))
        }
        for asset in package.assets:
            production = asset.get("production")
            view = production if isinstance(production, dict) else asset
            asset_id = cls._normalized_asset_id(view.get("asset_id"))
            if not asset_id:
                continue
            canonical = str(view.get("canonical_reference") or "").strip()
            canonical_many = view.get("canonical_references")
            if canonical or (isinstance(canonical_many, list | tuple) and canonical_many):
                required.add(asset_id)
        return required

    @classmethod
    def _require_character_role_alignment(
        cls,
        package: ProductionPackage,
        explicit_references: list[object],
    ) -> None:
        characters: list[tuple[str, str]] = []
        for asset in package.assets:
            production = asset.get("production")
            view = production if isinstance(production, dict) else asset
            if str(view.get("category") or "").strip().lower() != "character":
                continue
            asset_id = cls._normalized_asset_id(view.get("asset_id"))
            if asset_id:
                characters.append((asset_id, str(view.get("role") or "").strip().lower()))
        if not characters:
            return

        primary = next(
            (
                asset_id
                for asset_id, semantic_role in characters
                if any(
                    marker in semantic_role
                    for marker in ("dialogue speaker", "primary", "lead", "principal")
                )
            ),
            characters[0][0],
        )
        character_ids = {asset_id for asset_id, _role in characters}
        for item in explicit_references:
            if not isinstance(item, dict):
                continue
            asset_id = cls._normalized_asset_id(item.get("asset_id"))
            if asset_id not in character_ids:
                continue
            role = str(item.get("role") or "").strip().lower()
            if role == "group_identity":
                continue
            expected = "primary_identity" if asset_id == primary else "secondary_identity"
            if role != expected:
                raise GovernedReferenceSuitabilityError(
                    f"Explicit suitability reference for governed character {asset_id} uses role "
                    f"'{role or '<missing>'}', but current Shot semantics require '{expected}'."
                )

    @staticmethod
    def _normalized_asset_id(value: object) -> str:
        return str(value or "").strip().upper()
