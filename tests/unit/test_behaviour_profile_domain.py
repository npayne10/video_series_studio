"""Unit coverage for Phase 19.2.1 Behaviour Profile domain contracts."""

import pytest
from pydantic import ValidationError

from vscs.domain.assets import AssetCategory
from vscs.domain.behaviours import (
    BehaviourAuthority,
    BehaviourCategory,
    BehaviourConditionOperator,
    BehaviourConstraint,
    BehaviourInteractionRequirement,
    BehaviourOutcome,
    BehaviourParameter,
    BehaviourParameterType,
    BehaviourPrecondition,
    BehaviourProfile,
    BehaviourProvenance,
    is_production_behaviour_authority,
)


def _profile(**overrides: object) -> BehaviourProfile:
    values: dict[str, object] = {
        "profile_id": "BEP-SHP-DOCK",
        "name": "Controlled Docking",
        "description": "Controlled approach, alignment and docking with a compatible berth.",
        "category": BehaviourCategory.MANEUVERING,
        "action": "dock",
        "applicable_asset_categories": (AssetCategory.SHIP, AssetCategory.VEHICLE),
        "parameters": (
            BehaviourParameter(
                name="approach_speed",
                parameter_type=BehaviourParameterType.SPEED,
                description="Maximum commanded approach speed.",
                unit="m/s",
                minimum=0.0,
                maximum=5.0,
            ),
        ),
        "preconditions": (
            BehaviourPrecondition(
                subject="docking_port_available",
                operator=BehaviourConditionOperator.EQUALS,
                value=True,
            ),
        ),
        "constraints": (
            BehaviourConstraint(rule="Maintain positive clearance until final capture."),
        ),
        "outcomes": (
            BehaviourOutcome(
                name="Docked",
                resulting_state="docked",
            ),
        ),
        "interactions": (
            BehaviourInteractionRequirement(
                role="Docking target",
                required_asset_categories=(AssetCategory.SHIP, AssetCategory.LOCATION),
                required_capabilities=("docking interface",),
            ),
        ),
        "tags": ("spaceflight", " docking ", "spaceflight"),
        "authority": BehaviourAuthority.APPROVED,
        "provenance": BehaviourProvenance(source="Human production design"),
        "metadata": {" discipline ": " flight dynamics ", "": "ignored"},
    }
    values.update(overrides)
    return BehaviourProfile.model_validate(values)


def test_behaviour_profile_represents_provider_neutral_production_behaviour() -> None:
    profile = _profile()

    assert profile.profile_id == "BEP-SHP-DOCK"
    assert profile.action == "dock"
    assert profile.applicable_asset_categories == (AssetCategory.SHIP, AssetCategory.VEHICLE)
    assert profile.parameters[0].name == "approach_speed"
    assert profile.preconditions[0].value is True
    assert profile.outcomes[0].resulting_state == "docked"
    assert profile.interactions[0].required_capabilities == ("docking interface",)
    assert profile.tags == ("spaceflight", "docking")
    assert profile.metadata == {"discipline": "flight dynamics"}


def test_profile_id_and_action_are_normalized() -> None:
    profile = _profile(profile_id="bep-shp-land", action="Atmospheric Landing")

    assert profile.profile_id == "BEP-SHP-LAND"
    assert profile.action == "atmospheric_landing"


def test_profile_requires_at_least_one_applicable_asset_category() -> None:
    with pytest.raises(ValidationError, match="at least one asset category"):
        _profile(applicable_asset_categories=())


def test_profile_rejects_duplicate_parameter_names_after_normalization() -> None:
    with pytest.raises(ValidationError, match="parameter names must be unique"):
        _profile(
            parameters=(
                BehaviourParameter(name="speed", parameter_type=BehaviourParameterType.SPEED),
                BehaviourParameter(name="Speed", parameter_type=BehaviourParameterType.NUMBER),
            )
        )


def test_enum_parameter_requires_allowed_values() -> None:
    with pytest.raises(ValidationError, match="require allowed_values"):
        BehaviourParameter(name="mode", parameter_type=BehaviourParameterType.ENUM)


def test_non_enum_parameter_rejects_allowed_values() -> None:
    with pytest.raises(ValidationError, match="only valid for enum"):
        BehaviourParameter(
            name="speed",
            parameter_type=BehaviourParameterType.SPEED,
            allowed_values=("slow", "fast"),
        )


def test_parameter_rejects_inverted_numeric_bounds() -> None:
    with pytest.raises(ValidationError, match="minimum cannot exceed maximum"):
        BehaviourParameter(
            name="speed",
            parameter_type=BehaviourParameterType.SPEED,
            minimum=10.0,
            maximum=2.0,
        )


def test_precondition_value_rules_are_deterministic() -> None:
    exists = BehaviourPrecondition(
        subject="landing_gear",
        operator=BehaviourConditionOperator.EXISTS,
    )
    assert exists.value is None

    with pytest.raises(ValidationError, match="must not define a value"):
        BehaviourPrecondition(
            subject="landing_gear",
            operator=BehaviourConditionOperator.EXISTS,
            value=True,
        )

    with pytest.raises(ValidationError, match="requires a value"):
        BehaviourPrecondition(
            subject="altitude",
            operator=BehaviourConditionOperator.LESS_THAN,
        )


def test_only_approved_and_canonical_profiles_are_production_authority() -> None:
    assert not is_production_behaviour_authority(BehaviourAuthority.DRAFT)
    assert not is_production_behaviour_authority(BehaviourAuthority.PROPOSED)
    assert is_production_behaviour_authority(BehaviourAuthority.APPROVED)
    assert is_production_behaviour_authority(BehaviourAuthority.CANONICAL)


def test_profile_is_immutable_domain_state() -> None:
    profile = _profile()

    with pytest.raises(ValidationError):
        profile.name = "Changed"  # type: ignore[misc]
