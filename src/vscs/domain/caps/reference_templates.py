"""Category-specific canonical reference template models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from vscs.domain.assets import AssetCategory
from vscs.domain.caps.production_contract import CanonicalReferenceView


class ReferenceRequirement(StrEnum):
    """Production importance of a category reference view."""

    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class CategoryReferenceTemplate(BaseModel):
    """Reference coverage contract for one production asset category."""

    model_config = ConfigDict(frozen=True)

    category: AssetCategory
    required_views: tuple[CanonicalReferenceView, ...] = (CanonicalReferenceView.MASTER,)
    recommended_views: tuple[CanonicalReferenceView, ...] = ()
    optional_views: tuple[CanonicalReferenceView, ...] = ()
    notes: str = ""

    @model_validator(mode="after")
    def validate_view_sets(self) -> CategoryReferenceTemplate:
        required = set(self.required_views)
        recommended = set(self.recommended_views)
        optional = set(self.optional_views)
        if CanonicalReferenceView.MASTER not in required:
            raise ValueError("Every category reference template must require the MASTER view")
        if required & recommended or required & optional or recommended & optional:
            raise ValueError("Required, recommended and optional reference views must be disjoint")
        return self

    def requirement_for(self, view: CanonicalReferenceView) -> ReferenceRequirement | None:
        """Return the configured requirement level, or None when the view is not applicable."""
        if view in self.required_views:
            return ReferenceRequirement.REQUIRED
        if view in self.recommended_views:
            return ReferenceRequirement.RECOMMENDED
        if view in self.optional_views:
            return ReferenceRequirement.OPTIONAL
        return None

    @property
    def applicable_views(self) -> tuple[CanonicalReferenceView, ...]:
        """Return all views governed by this template in deterministic priority order."""
        return (*self.required_views, *self.recommended_views, *self.optional_views)


class ReferenceCoverage(BaseModel):
    """Current active-reference coverage against one category template."""

    model_config = ConfigDict(frozen=True)

    category: AssetCategory
    template: CategoryReferenceTemplate
    present_views: tuple[CanonicalReferenceView, ...] = ()
    missing_required: tuple[CanonicalReferenceView, ...] = ()
    missing_recommended: tuple[CanonicalReferenceView, ...] = ()
    present_optional: tuple[CanonicalReferenceView, ...] = ()

    @property
    def required_complete(self) -> bool:
        return not self.missing_required

    @property
    def recommended_complete(self) -> bool:
        return not self.missing_recommended


class CategoryReferenceTemplateRegistry:
    """Replaceable registry for default and future project-specific templates."""

    def __init__(self, templates: tuple[CategoryReferenceTemplate, ...] = ()) -> None:
        self._templates: dict[AssetCategory, CategoryReferenceTemplate] = {}
        for template in templates:
            self.register(template)

    def register(self, template: CategoryReferenceTemplate) -> None:
        """Register or intentionally replace the template for one category."""
        self._templates[template.category] = template

    def require(self, category: AssetCategory) -> CategoryReferenceTemplate:
        try:
            return self._templates[category]
        except KeyError as exc:
            raise KeyError(
                f"No canonical reference template is registered for {category.value}"
            ) from exc

    def categories(self) -> tuple[AssetCategory, ...]:
        return tuple(sorted(self._templates, key=lambda category: category.value))


def default_category_reference_templates() -> CategoryReferenceTemplateRegistry:
    """Return the VSCS baseline reference coverage contracts for every AssetCategory."""

    master_only = (
        AssetCategory.AUDIO,
        AssetCategory.CAMERA,
        AssetCategory.LIGHTING,
        AssetCategory.REFERENCE,
        AssetCategory.OTHER,
    )
    templates = [
        CategoryReferenceTemplate(
            category=AssetCategory.CHARACTER,
            required_views=(
                CanonicalReferenceView.MASTER,
                CanonicalReferenceView.FULL_BODY,
                CanonicalReferenceView.PROFILE_LEFT,
                CanonicalReferenceView.PROFILE_RIGHT,
                CanonicalReferenceView.FACE,
            ),
            recommended_views=(CanonicalReferenceView.FRONT, CanonicalReferenceView.REAR),
            optional_views=(CanonicalReferenceView.DETAIL, CanonicalReferenceView.VARIANT),
            notes="Identity coverage for face, body and both profiles.",
        ),
        CategoryReferenceTemplate(
            category=AssetCategory.SHIP,
            required_views=(
                CanonicalReferenceView.MASTER,
                CanonicalReferenceView.FRONT,
                CanonicalReferenceView.REAR,
                CanonicalReferenceView.PORT,
                CanonicalReferenceView.STARBOARD,
                CanonicalReferenceView.TOP,
                CanonicalReferenceView.BOTTOM,
            ),
            recommended_views=(
                CanonicalReferenceView.PRIMARY_THREE_QUARTER,
                CanonicalReferenceView.DETAIL,
            ),
            optional_views=(CanonicalReferenceView.INTERIOR, CanonicalReferenceView.VARIANT),
            notes="Exterior turnaround sufficient for camera-angle selection and continuity.",
        ),
        CategoryReferenceTemplate(
            category=AssetCategory.VEHICLE,
            required_views=(
                CanonicalReferenceView.MASTER,
                CanonicalReferenceView.FRONT,
                CanonicalReferenceView.REAR,
                CanonicalReferenceView.LEFT,
                CanonicalReferenceView.RIGHT,
                CanonicalReferenceView.TOP,
            ),
            recommended_views=(
                CanonicalReferenceView.PRIMARY_THREE_QUARTER,
                CanonicalReferenceView.DETAIL,
            ),
            optional_views=(
                CanonicalReferenceView.BOTTOM,
                CanonicalReferenceView.INTERIOR,
                CanonicalReferenceView.VARIANT,
            ),
        ),
        CategoryReferenceTemplate(
            category=AssetCategory.PROP,
            required_views=(
                CanonicalReferenceView.MASTER,
                CanonicalReferenceView.FRONT,
                CanonicalReferenceView.REAR,
                CanonicalReferenceView.LEFT,
                CanonicalReferenceView.RIGHT,
            ),
            recommended_views=(CanonicalReferenceView.TOP, CanonicalReferenceView.DETAIL),
            optional_views=(CanonicalReferenceView.BOTTOM, CanonicalReferenceView.VARIANT),
        ),
        CategoryReferenceTemplate(
            category=AssetCategory.LOCATION,
            required_views=(
                CanonicalReferenceView.MASTER,
                CanonicalReferenceView.PRIMARY_THREE_QUARTER,
            ),
            recommended_views=(CanonicalReferenceView.AERIAL, CanonicalReferenceView.DETAIL),
            optional_views=(
                CanonicalReferenceView.INTERIOR,
                CanonicalReferenceView.SURFACE,
                CanonicalReferenceView.VARIANT,
            ),
            notes="Interior/surface views remain optional because location subtypes differ.",
        ),
        CategoryReferenceTemplate(
            category=AssetCategory.ENVIRONMENT,
            required_views=(
                CanonicalReferenceView.MASTER,
                CanonicalReferenceView.PRIMARY_THREE_QUARTER,
            ),
            recommended_views=(CanonicalReferenceView.AERIAL, CanonicalReferenceView.SURFACE),
            optional_views=(CanonicalReferenceView.DETAIL, CanonicalReferenceView.VARIANT),
        ),
        CategoryReferenceTemplate(
            category=AssetCategory.PLANET,
            required_views=(
                CanonicalReferenceView.MASTER,
                CanonicalReferenceView.ORBIT,
                CanonicalReferenceView.SURFACE,
            ),
            recommended_views=(CanonicalReferenceView.AERIAL, CanonicalReferenceView.DETAIL),
            optional_views=(CanonicalReferenceView.VARIANT,),
        ),
        CategoryReferenceTemplate(
            category=AssetCategory.UNIFORM,
            required_views=(
                CanonicalReferenceView.MASTER,
                CanonicalReferenceView.FRONT,
                CanonicalReferenceView.REAR,
                CanonicalReferenceView.PROFILE_LEFT,
                CanonicalReferenceView.PROFILE_RIGHT,
            ),
            recommended_views=(CanonicalReferenceView.FULL_BODY, CanonicalReferenceView.DETAIL),
            optional_views=(CanonicalReferenceView.VARIANT,),
        ),
        CategoryReferenceTemplate(
            category=AssetCategory.TECHNOLOGY,
            required_views=(
                CanonicalReferenceView.MASTER,
                CanonicalReferenceView.FRONT,
                CanonicalReferenceView.REAR,
                CanonicalReferenceView.LEFT,
                CanonicalReferenceView.RIGHT,
            ),
            recommended_views=(CanonicalReferenceView.TOP, CanonicalReferenceView.DETAIL),
            optional_views=(CanonicalReferenceView.INTERIOR, CanonicalReferenceView.VARIANT),
        ),
        CategoryReferenceTemplate(
            category=AssetCategory.EFFECT,
            required_views=(CanonicalReferenceView.MASTER,),
            recommended_views=(CanonicalReferenceView.VARIANT,),
            optional_views=(CanonicalReferenceView.DETAIL,),
            notes="Effects vary temporally; additional visual references are advisory rather than mandatory.",
        ),
    ]
    templates.extend(CategoryReferenceTemplate(category=category) for category in master_only)
    return CategoryReferenceTemplateRegistry(tuple(templates))
