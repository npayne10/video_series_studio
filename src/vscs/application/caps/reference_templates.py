"""Application service for category reference templates and active coverage."""

from __future__ import annotations

from vscs.application.caps.reference_library import ReferenceLibraryService
from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.domain.caps import CanonicalReferenceLifecycle, CanonicalReferenceView
from vscs.domain.caps.reference_templates import (
    CategoryReferenceTemplate,
    CategoryReferenceTemplateRegistry,
    ReferenceCoverage,
    default_category_reference_templates,
)


class CategoryReferenceTemplateService:
    """Resolve a category template and compare it with active CAP references."""

    def __init__(
        self,
        references: CanonicalReferenceService,
        library: ReferenceLibraryService,
        registry: CategoryReferenceTemplateRegistry | None = None,
    ) -> None:
        self.references = references
        self.library = library
        self.registry = registry or default_category_reference_templates()

    def template_for(self, asset_id: str) -> CategoryReferenceTemplate:
        asset = self.references.caps.assets.get(asset_id)
        return self.registry.require(asset.category)

    def coverage(self, asset_id: str) -> ReferenceCoverage:
        asset = self.references.caps.assets.get(asset_id)
        template = self.registry.require(asset.category)
        active_views = {
            entry.view
            for entry in self.library.list_for_cap(asset_id)
            if entry.lifecycle
            not in {
                CanonicalReferenceLifecycle.ARCHIVED,
                CanonicalReferenceLifecycle.REJECTED,
            }
        }
        missing_required = tuple(
            view for view in template.required_views if view not in active_views
        )
        missing_recommended = tuple(
            view for view in template.recommended_views if view not in active_views
        )
        present_optional = tuple(
            view for view in template.optional_views if view in active_views
        )
        present_views = tuple(
            view for view in template.applicable_views if view in active_views
        )
        return ReferenceCoverage(
            category=asset.category,
            template=template,
            present_views=present_views,
            missing_required=missing_required,
            missing_recommended=missing_recommended,
            present_optional=present_optional,
        )

    def missing_required_views(self, asset_id: str) -> tuple[CanonicalReferenceView, ...]:
        """Return only generatable missing required views; MASTER is externally authored."""
        coverage = self.coverage(asset_id)
        return tuple(
            view
            for view in coverage.missing_required
            if view is not CanonicalReferenceView.MASTER
        )
