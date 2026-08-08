"""Deterministic CAP readiness evaluation service."""

from __future__ import annotations

from typing import ClassVar

from vscs.application.caps.reference_library import ReferenceLibraryService
from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.application.caps.reference_templates import CategoryReferenceTemplateService
from vscs.application.caps.service import CAPService
from vscs.domain.assets import AssetCategory
from vscs.domain.caps import CanonicalReferenceLifecycle, CanonicalReferenceView, CAPStatus
from vscs.domain.caps.readiness import (
    ReadinessAssessment,
    ReadinessDimension,
    ReadinessGap,
    ReadinessReport,
    ReadinessSeverity,
    ReadinessState,
)

_APPROVED_REFERENCE_STATES = {
    CanonicalReferenceLifecycle.APPROVED,
    CanonicalReferenceLifecycle.LOCKED,
}
_FUNCTIONAL_IDENTITY_CATEGORIES = {
    AssetCategory.PROP,
    AssetCategory.SHIP,
    AssetCategory.VEHICLE,
    AssetCategory.TECHNOLOGY,
}
_CONSTRAINT_CATEGORIES = {
    AssetCategory.CHARACTER,
    AssetCategory.PROP,
    AssetCategory.SHIP,
    AssetCategory.VEHICLE,
    AssetCategory.UNIFORM,
    AssetCategory.TECHNOLOGY,
}
_VISUAL_IDENTITY_CATEGORIES = {
    AssetCategory.CHARACTER,
    AssetCategory.LOCATION,
    AssetCategory.PROP,
    AssetCategory.SHIP,
    AssetCategory.VEHICLE,
    AssetCategory.ENVIRONMENT,
    AssetCategory.PLANET,
    AssetCategory.UNIFORM,
    AssetCategory.TECHNOLOGY,
}


class CAPReadinessService:
    """Single deterministic authority for CAP readiness decisions."""

    _WEIGHTS: ClassVar[dict[ReadinessDimension, int]] = {
        ReadinessDimension.IDENTITY: 25,
        ReadinessDimension.REFERENCES: 30,
        ReadinessDimension.GENERATION: 20,
        ReadinessDimension.PRODUCTION: 25,
    }

    def __init__(
        self,
        caps: CAPService,
        references: CanonicalReferenceService,
        library: ReferenceLibraryService | None = None,
        templates: CategoryReferenceTemplateService | None = None,
    ) -> None:
        self.caps = caps
        self.references = references
        self.library = library or ReferenceLibraryService(references)
        self.templates = templates or CategoryReferenceTemplateService(references, self.library)

    def evaluate(self, asset_id: str) -> ReadinessReport:
        """Evaluate one CAP from persisted canonical data only."""
        cap = self.caps.get(asset_id)
        asset = self.caps.assets.get(asset_id)
        entries = self.library.list_for_cap(asset_id)

        identity = self._identity(cap, entries, asset.category)
        references = self._references(asset_id, entries)
        generation = self._generation(cap.status, identity, references)
        production = self._production(cap, asset.category, generation)
        overall_score = round(
            sum(
                assessment.score * self._WEIGHTS[assessment.dimension]
                for assessment in (identity, references, generation, production)
            )
            / 100
        )
        return ReadinessReport(
            asset_id=asset.asset_id,
            identity=identity,
            references=references,
            generation=generation,
            production=production,
            overall_score=overall_score,
        )

    def evaluate_all(self) -> tuple[ReadinessReport, ...]:
        """Evaluate every persisted CAP in deterministic asset-ID order."""
        return tuple(
            self.evaluate(profile.asset_id)
            for profile in sorted(self.caps.list(), key=lambda item: item.asset_id)
        )

    def overall_percentage(self, asset_id: str) -> int:
        return self.evaluate(asset_id).overall_score

    def blocking_gaps(self, asset_id: str) -> tuple[ReadinessGap, ...]:
        return self.evaluate(asset_id).blocking_gaps

    def _identity(
        self, cap: object, entries: tuple[object, ...], category: AssetCategory
    ) -> ReadinessAssessment:
        gaps: list[ReadinessGap] = []
        checks = 3
        passed = 0
        if str(getattr(cap, "title", "")).strip():
            passed += 1
        else:
            gaps.append(
                self._gap("identity.name", ReadinessDimension.IDENTITY, "Canonical name is missing")
            )
        if str(getattr(cap, "canonical_description", "")).strip():
            passed += 1
        else:
            gaps.append(
                self._gap(
                    "identity.description",
                    ReadinessDimension.IDENTITY,
                    "Canonical description is missing",
                )
            )
        master = next(
            (
                entry
                for entry in entries
                if getattr(entry, "view", None) is CanonicalReferenceView.MASTER
                and getattr(entry, "lifecycle", None) is CanonicalReferenceLifecycle.LOCKED
            ),
            None,
        )
        if master is not None:
            passed += 1
        else:
            gaps.append(
                self._gap(
                    "identity.master_locked",
                    ReadinessDimension.IDENTITY,
                    "Approved ChatGPT MASTER is not locked",
                )
            )
        if (
            category in _VISUAL_IDENTITY_CATEGORIES
            and not str(getattr(cap, "visual_identity", "")).strip()
        ):
            checks += 1
            gaps.append(
                self._gap(
                    "identity.visual_identity",
                    ReadinessDimension.IDENTITY,
                    "Visual identity is not defined",
                    severity=ReadinessSeverity.WARNING,
                )
            )
        elif category in _VISUAL_IDENTITY_CATEGORIES:
            checks += 1
            passed += 1
        score = round(passed * 100 / checks)
        state = (
            ReadinessState.READY
            if not any(gap.severity is ReadinessSeverity.BLOCKING for gap in gaps)
            else (ReadinessState.PARTIAL if score else ReadinessState.NOT_READY)
        )
        return ReadinessAssessment(
            dimension=ReadinessDimension.IDENTITY,
            state=state,
            score=score,
            gaps=tuple(gaps),
        )

    def _references(self, asset_id: str, entries: tuple[object, ...]) -> ReadinessAssessment:
        template = self.templates.template_for(asset_id)
        lifecycle_by_view = {
            getattr(entry, "view", None): getattr(entry, "lifecycle", None) for entry in entries
        }
        required_ready = [
            view
            for view in template.required_views
            if lifecycle_by_view.get(view) in _APPROVED_REFERENCE_STATES
        ]
        recommended_ready = [
            view
            for view in template.recommended_views
            if lifecycle_by_view.get(view) in _APPROVED_REFERENCE_STATES
        ]
        gaps: list[ReadinessGap] = []
        for view in template.required_views:
            lifecycle = lifecycle_by_view.get(view)
            if lifecycle in _APPROVED_REFERENCE_STATES:
                continue
            label = view.value.replace("_", " ").title()
            message = (
                f"Required reference {label} is awaiting approval"
                if lifecycle is CanonicalReferenceLifecycle.CANDIDATE
                else f"Required reference {label} is missing or not approved"
            )
            gaps.append(
                self._gap(
                    f"references.required.{view.value}",
                    ReadinessDimension.REFERENCES,
                    message,
                )
            )
        master_state = lifecycle_by_view.get(CanonicalReferenceView.MASTER)
        if master_state is not CanonicalReferenceLifecycle.LOCKED:
            gaps.append(
                self._gap(
                    "references.master_locked",
                    ReadinessDimension.REFERENCES,
                    "MASTER reference must be Locked for production",
                )
            )

        required_ratio = (
            len(required_ready) / len(template.required_views) if template.required_views else 1.0
        )
        if template.recommended_views:
            recommended_ratio = len(recommended_ready) / len(template.recommended_views)
            score = round(required_ratio * 80 + recommended_ratio * 20)
        else:
            score = round(required_ratio * 100)
        blocking = any(gap.severity is ReadinessSeverity.BLOCKING for gap in gaps)
        state = (
            ReadinessState.READY
            if not blocking
            else (ReadinessState.PARTIAL if score else ReadinessState.NOT_READY)
        )
        return ReadinessAssessment(
            dimension=ReadinessDimension.REFERENCES,
            state=state,
            score=score,
            gaps=tuple(gaps),
        )

    def _generation(
        self,
        cap_status: CAPStatus,
        identity: ReadinessAssessment,
        references: ReadinessAssessment,
    ) -> ReadinessAssessment:
        gaps: list[ReadinessGap] = []
        if cap_status is not CAPStatus.APPROVED:
            gaps.append(
                self._gap(
                    "generation.cap_approved",
                    ReadinessDimension.GENERATION,
                    "CAP must be Approved before production generation",
                )
            )
        if not identity.ready:
            gaps.append(
                self._gap(
                    "generation.identity",
                    ReadinessDimension.GENERATION,
                    "Identity Readiness is not Ready",
                )
            )
        if not references.ready:
            gaps.append(
                self._gap(
                    "generation.references",
                    ReadinessDimension.GENERATION,
                    "Reference Readiness is not Ready",
                )
            )
        score = round(
            (int(cap_status is CAPStatus.APPROVED) + int(identity.ready) + int(references.ready))
            * 100
            / 3
        )
        return ReadinessAssessment(
            dimension=ReadinessDimension.GENERATION,
            state=ReadinessState.READY if not gaps else ReadinessState.BLOCKED,
            score=score,
            gaps=tuple(gaps),
        )

    def _production(
        self,
        cap: object,
        category: AssetCategory,
        generation: ReadinessAssessment,
    ) -> ReadinessAssessment:
        gaps: list[ReadinessGap] = []
        checks = 2
        passed = 0
        if generation.ready:
            passed += 1
        else:
            gaps.append(
                self._gap(
                    "production.generation",
                    ReadinessDimension.PRODUCTION,
                    "Generation Readiness is blocked",
                )
            )
        if str(getattr(cap, "production_notes", "")).strip():
            passed += 1
        else:
            gaps.append(
                self._gap(
                    "production.guidance",
                    ReadinessDimension.PRODUCTION,
                    "Production guidance is not defined",
                    severity=ReadinessSeverity.WARNING,
                )
            )

        functional_identity = tuple(getattr(cap, "functional_identity", ()) or ())
        if category in _FUNCTIONAL_IDENTITY_CATEGORIES:
            checks += 1
            if functional_identity:
                passed += 1
            else:
                gaps.append(
                    self._gap(
                        "production.functional_identity",
                        ReadinessDimension.PRODUCTION,
                        "Structured functional capabilities are required for this category",
                    )
                )

        constraints = tuple(getattr(cap, "constraints", ()) or ())
        if category in _CONSTRAINT_CATEGORIES:
            checks += 1
            if constraints:
                passed += 1
            else:
                gaps.append(
                    self._gap(
                        "production.constraints",
                        ReadinessDimension.PRODUCTION,
                        "Structured canonical constraints are required for this category",
                    )
                )

        score = round(passed * 100 / checks)
        blocking = any(gap.severity is ReadinessSeverity.BLOCKING for gap in gaps)
        state = ReadinessState.READY if not blocking else ReadinessState.BLOCKED
        return ReadinessAssessment(
            dimension=ReadinessDimension.PRODUCTION,
            state=state,
            score=score,
            gaps=tuple(gaps),
        )

    @staticmethod
    def _gap(
        code: str,
        dimension: ReadinessDimension,
        message: str,
        *,
        severity: ReadinessSeverity = ReadinessSeverity.BLOCKING,
    ) -> ReadinessGap:
        return ReadinessGap(
            code=code,
            dimension=dimension,
            severity=severity,
            message=message,
        )
