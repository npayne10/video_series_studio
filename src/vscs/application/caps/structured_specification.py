"""Phase 20.19.3B: governed, category-aware CAP specification drafts.

The existing CAP production_metadata JSON column is the storage envelope.
No schema migration, implicit approval, image creation or provider submission.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vscs.application.caps.anchor_placement import AnchorPlacement
from vscs.application.caps.geometry_contract import CAPGeometry
from vscs.application.caps.service import CAPService
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CAPStatus, CAPUpdate

SPECIFICATION_METADATA_KEY = "vscs.structured_cap_specification.v1"
SCHEMA_VERSION = 1

_CATEGORY_FIELDS: dict[AssetCategory, frozenset[str]] = {
    AssetCategory.CHARACTER: frozenset(
        {"anatomy", "face", "eyes", "hair", "skin", "proportions", "costume", "insignia"}
    ),
    AssetCategory.LOCATION: frozenset(
        {
            "layout",
            "scale",
            "architecture",
            "materials",
            "fixtures",
            "spatial_anchors",
            "windows",
            "doors",
        }
    ),
    AssetCategory.SHIP: frozenset(
        {"dimensions", "silhouette", "hull", "markings", "propulsion", "interior_relationships"}
    ),
    AssetCategory.VEHICLE: frozenset(
        {"dimensions", "silhouette", "hull", "markings", "propulsion", "interior_relationships"}
    ),
    AssetCategory.PROP: frozenset(
        {"geometry", "materials", "components", "controls", "display", "operating_states"}
    ),
    AssetCategory.TECHNOLOGY: frozenset(
        {"geometry", "materials", "components", "controls", "display", "operating_states"}
    ),
    AssetCategory.ENVIRONMENT: frozenset(
        {"terrain", "atmosphere", "sky", "climate", "illumination", "geography"}
    ),
    AssetCategory.PLANET: frozenset(
        {"terrain", "atmosphere", "sky", "climate", "illumination", "geography"}
    ),
    AssetCategory.UNIFORM: frozenset({"cut", "fabric", "colours", "insignia", "fit", "materials"}),
}


class DependencyRelation(StrEnum):
    CONTAINS = "contains"
    MOUNTED_IN = "mounted_in"
    ADJACENT_TO = "adjacent_to"
    LOCATED_IN = "located_in"
    REFERENCES = "references"


class DependencyConstraint(BaseModel):
    """Explicit, operator-reviewed spatial relationship; never inferred canon."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_asset_id: str = Field(min_length=1)
    relation: DependencyRelation
    anchor: str = ""
    minimum_clearance_mm: float | None = Field(default=None, ge=0)
    placement: AnchorPlacement | None = None

    @field_validator("target_asset_id")
    @classmethod
    def normalize_target_id(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def check_clearance(self) -> DependencyConstraint:
        if self.minimum_clearance_mm is not None and not self.anchor:
            raise ValueError("Clearance constraints require a named spatial anchor")
        return self


class CAPSpecificationError(ValueError):
    """Invalid or unauthorized structured specification operation."""


class CAPStructuredSpecification(BaseModel):
    """Authored, non-authoritative specification attached to a Draft CAP."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: int = Field(default=SCHEMA_VERSION, ge=1, le=SCHEMA_VERSION)
    asset_id: str = Field(min_length=1, max_length=64)
    category: AssetCategory
    subcategory: str = ""
    design_intent: str = Field(min_length=1)
    canonical_attributes: dict[str, str] = Field(min_length=1)
    allowed_variants: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    master_prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    continuity_rules: tuple[str, ...] = ()
    dependency_asset_ids: tuple[str, ...] = ()
    dependency_constraints: tuple[DependencyConstraint, ...] = ()
    geometry: CAPGeometry | None = None
    source_document_sha256: str | None = Field(
        default=None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    source_description: str = ""
    origin: str = "operator_draft"

    @field_validator("asset_id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.upper()

    @field_validator("canonical_attributes")
    @classmethod
    def validate_attributes(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key.strip() or not item.strip() for key, item in value.items()):
            raise ValueError("Canonical attributes need named, nonempty values")
        return value

    @field_validator("allowed_variants")
    @classmethod
    def validate_variants(cls, value: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        if any(
            not key.strip() or not items or any(not item.strip() for item in items)
            for key, items in value.items()
        ):
            raise ValueError("Allowed variant names and choices must not be empty")
        return value

    def validate_category_contract(self) -> None:
        if len(set(self.dependency_asset_ids)) != len(self.dependency_asset_ids):
            raise CAPSpecificationError("Duplicate dependency asset IDs")
        if len({item.target_asset_id for item in self.dependency_constraints}) != len(
            self.dependency_constraints
        ):
            raise CAPSpecificationError("Duplicate dependency relationship targets")
        if any(
            item.target_asset_id not in self.dependency_asset_ids
            for item in self.dependency_constraints
        ):
            raise CAPSpecificationError("Relationship targets must be declared dependencies")
        if self.asset_id in self.dependency_asset_ids:
            raise CAPSpecificationError("An asset cannot depend on itself")
        required = _CATEGORY_FIELDS.get(self.category)
        if required is not None and not (self.canonical_attributes.keys() & required):
            raise CAPSpecificationError(
                f"{self.category.value} specification needs at least one category-specific attribute "
                f"from {', '.join(sorted(required))}"
            )
        overlapping = self.canonical_attributes.keys() & self.allowed_variants.keys()
        if overlapping:
            raise CAPSpecificationError(
                "A canonical attribute cannot also be freely variable: "
                + ", ".join(sorted(overlapping))
            )

    def fingerprint(self) -> str:
        payload = self.model_dump_json(exclude_none=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CAPStructuredSpecificationService:
    """Persist Draft specifications via the existing project-scoped CAP repository."""

    def __init__(self, caps: CAPService) -> None:
        self.caps = caps

    def save_draft(self, specification: CAPStructuredSpecification) -> CAPStructuredSpecification:
        specification.validate_category_contract()
        asset = self.caps.assets.get(specification.asset_id)
        if asset.category != specification.category:
            raise CAPSpecificationError(
                "Specification category does not match the registered asset"
            )
        cap = self.caps.get(specification.asset_id)
        if cap.status != CAPStatus.DRAFT:
            raise CAPSpecificationError("Only Draft CAPs may receive specification drafts")
        metadata = dict(cap.production_metadata)
        serialized = specification.model_dump(mode="json", exclude_none=True)
        metadata[SPECIFICATION_METADATA_KEY] = json.dumps(
            serialized, sort_keys=True, separators=(",", ":")
        )
        self.caps.update(cap.asset_id, CAPUpdate(production_metadata=metadata))
        return specification

    def get(self, asset_id: str) -> CAPStructuredSpecification | None:
        cap = self.caps.get(asset_id)
        raw = cap.production_metadata.get(SPECIFICATION_METADATA_KEY)
        if raw is None:
            return None
        try:
            data: Any = json.loads(raw)
            specification = CAPStructuredSpecification.model_validate(data)
        except (ValueError, TypeError) as exc:
            raise CAPSpecificationError("Stored specification is invalid") from exc
        if specification.asset_id != cap.asset_id:
            raise CAPSpecificationError("Stored specification asset identity mismatch")
        specification.validate_category_contract()
        return specification
