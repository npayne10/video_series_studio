"""Provider-neutral domain model for VSCS Behaviour Profiles."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vscs.domain.assets import AssetCategory


class BehaviourAuthority(StrEnum):
    """Governance authority for a Behaviour Profile."""

    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    CANONICAL = "canonical"


class BehaviourCategory(StrEnum):
    """High-level production behaviour classifications."""

    LOCOMOTION = "locomotion"
    NAVIGATION = "navigation"
    MANEUVERING = "maneuvering"
    INTERACTION = "interaction"
    OPERATION = "operation"
    COMMUNICATION = "communication"
    PERFORMANCE = "performance"
    PHYSICAL = "physical"
    TRANSITION = "transition"
    EFFECT = "effect"
    OTHER = "other"


class BehaviourParameterType(StrEnum):
    """Supported machine-readable behaviour parameter types."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DURATION = "duration"
    DISTANCE = "distance"
    SPEED = "speed"
    ANGLE = "angle"
    ENUM = "enum"
    ASSET_REFERENCE = "asset_reference"


class BehaviourConditionOperator(StrEnum):
    """Operators supported by deterministic behaviour preconditions."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class BehaviourConstraintSeverity(StrEnum):
    """Production significance of a Behaviour Profile constraint."""

    REQUIRED = "required"
    WARNING = "warning"
    ADVISORY = "advisory"


class BehaviourParameter(BaseModel):
    """One configurable input to a behaviour."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=64)
    parameter_type: BehaviourParameterType
    description: str = ""
    required: bool = False
    default: Any | None = None
    unit: str | None = None
    allowed_values: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", normalized):
            raise ValueError("Behaviour parameter names must use lower_snake_case")
        return normalized

    @field_validator("allowed_values")
    @classmethod
    def normalize_allowed_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.strip() for item in value if item.strip()))

    @model_validator(mode="after")
    def validate_bounds_and_enum(self) -> "BehaviourParameter":
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Behaviour parameter minimum cannot exceed maximum")
        if self.parameter_type is BehaviourParameterType.ENUM and not self.allowed_values:
            raise ValueError("Enum behaviour parameters require allowed_values")
        if self.parameter_type is not BehaviourParameterType.ENUM and self.allowed_values:
            raise ValueError("allowed_values are only valid for enum behaviour parameters")
        return self


class BehaviourPrecondition(BaseModel):
    """Deterministic condition that must hold before a behaviour can occur."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=128)
    operator: BehaviourConditionOperator
    value: str | int | float | bool | tuple[str, ...] | None = None
    description: str = ""

    @model_validator(mode="after")
    def validate_value_requirement(self) -> "BehaviourPrecondition":
        existence_operators = {
            BehaviourConditionOperator.EXISTS,
            BehaviourConditionOperator.NOT_EXISTS,
        }
        if self.operator in existence_operators and self.value is not None:
            raise ValueError("Existence preconditions must not define a value")
        if self.operator not in existence_operators and self.value is None:
            raise ValueError("This precondition operator requires a value")
        return self


class BehaviourConstraint(BaseModel):
    """Canonical rule governing how a behaviour may be performed."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    rule: str = Field(min_length=1)
    rationale: str = ""
    severity: BehaviourConstraintSeverity = BehaviourConstraintSeverity.REQUIRED


class BehaviourOutcome(BaseModel):
    """Observable result or state change caused by a behaviour."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    resulting_state: str | None = None


class BehaviourInteractionRequirement(BaseModel):
    """Counterpart or environmental requirement for an interaction behaviour."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    role: str = Field(min_length=1, max_length=128)
    description: str = ""
    required_asset_categories: tuple[AssetCategory, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    optional: bool = False

    @field_validator("required_capabilities")
    @classmethod
    def normalize_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.strip() for item in value if item.strip()))


class BehaviourProvenance(BaseModel):
    """Traceable origin for a Behaviour Profile definition."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    source: str = ""
    source_reference: str | None = None
    authored_by: str | None = None
    notes: str = ""


class BehaviourProfile(BaseModel):
    """Canonical description of how one or more production asset classes behave."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    schema_version: int = Field(default=1, ge=1)
    profile_id: str = Field(min_length=1, max_length=96)
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(default="1.0", min_length=1, max_length=32)
    description: str = ""
    category: BehaviourCategory
    action: str = Field(min_length=1, max_length=96)
    applicable_asset_categories: tuple[AssetCategory, ...]
    aliases: tuple[str, ...] = ()
    parameters: tuple[BehaviourParameter, ...] = ()
    preconditions: tuple[BehaviourPrecondition, ...] = ()
    constraints: tuple[BehaviourConstraint, ...] = ()
    outcomes: tuple[BehaviourOutcome, ...] = ()
    interactions: tuple[BehaviourInteractionRequirement, ...] = ()
    tags: tuple[str, ...] = ()
    authority: BehaviourAuthority = BehaviourAuthority.DRAFT
    provenance: BehaviourProvenance = Field(default_factory=BehaviourProvenance)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("profile_id")
    @classmethod
    def normalize_profile_id(cls, value: str) -> str:
        normalized = value.strip().upper().replace(" ", "-")
        if not re.fullmatch(r"BEP-[A-Z0-9][A-Z0-9_-]*", normalized):
            raise ValueError("Behaviour Profile IDs must start with 'BEP-' and use letters, numbers, '-' or '_'")
        return normalized

    @field_validator("action")
    @classmethod
    def normalize_action(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_.-]*", normalized):
            raise ValueError("Behaviour actions must be stable lower-case machine identifiers")
        return normalized

    @field_validator("applicable_asset_categories")
    @classmethod
    def require_asset_categories(
        cls, value: tuple[AssetCategory, ...]
    ) -> tuple[AssetCategory, ...]:
        normalized = tuple(dict.fromkeys(value))
        if not normalized:
            raise ValueError("A Behaviour Profile must apply to at least one asset category")
        return normalized

    @field_validator("aliases", "tags")
    @classmethod
    def normalize_terms(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.strip() for item in value if item.strip()))

    @field_validator("metadata")
    @classmethod
    def normalize_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            str(key).strip(): str(item).strip()
            for key, item in value.items()
            if str(key).strip() and str(item).strip()
        }

    @model_validator(mode="after")
    def validate_unique_parameter_names(self) -> "BehaviourProfile":
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("Behaviour Profile parameter names must be unique")
        return self


def is_production_behaviour_authority(authority: BehaviourAuthority) -> bool:
    """Return whether a Behaviour Profile may be consumed as production authority."""

    return authority in {BehaviourAuthority.APPROVED, BehaviourAuthority.CANONICAL}
