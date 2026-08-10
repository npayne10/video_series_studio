"""Repository coverage for Phase 19.2.2 Behaviour Profile persistence."""

from pathlib import Path

import pytest
from sqlalchemy import text

from vscs.application.behaviours import (
    BehaviourProfileRepository,
    BehaviourProfileRepositoryError,
)
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
)
from vscs.domain.projects import ProjectMetadata
from vscs.infrastructure.database import DatabaseManager


def _open_database(tmp_path: Path) -> DatabaseManager:
    database = DatabaseManager()
    database.open(tmp_path, ProjectMetadata(name="Behaviour Persistence"))
    return database


def _profile(
    *,
    version: str = "1.0",
    authority: BehaviourAuthority = BehaviourAuthority.DRAFT,
) -> BehaviourProfile:
    return BehaviourProfile(
        profile_id="BEP-SHP-DOCK",
        name="Ship Docking",
        version=version,
        description="Controlled docking behaviour for compatible spacecraft.",
        category=BehaviourCategory.MANEUVERING,
        action="dock",
        applicable_asset_categories=(AssetCategory.SHIP, AssetCategory.VEHICLE),
        aliases=("berth", "dock"),
        parameters=(
            BehaviourParameter(
                name="approach_speed",
                parameter_type=BehaviourParameterType.SPEED,
                description="Final controlled approach speed.",
                required=True,
                unit="m/s",
                minimum=0.0,
                maximum=5.0,
            ),
        ),
        preconditions=(
            BehaviourPrecondition(
                subject="docking_port_available",
                operator=BehaviourConditionOperator.EQUALS,
                value=True,
            ),
        ),
        constraints=(
            BehaviourConstraint(
                rule="Maintain docking-axis alignment during final approach.",
                rationale="Physical docking compatibility.",
            ),
        ),
        outcomes=(
            BehaviourOutcome(
                name="docked",
                description="Vessel is mechanically secured.",
                resulting_state="docked",
            ),
        ),
        interactions=(
            BehaviourInteractionRequirement(
                role="docking_target",
                description="Target station or vessel.",
                required_asset_categories=(AssetCategory.SHIP, AssetCategory.LOCATION),
                required_capabilities=("accept docking",),
            ),
        ),
        tags=("spacecraft", "precision"),
        authority=authority,
        provenance=BehaviourProvenance(
            source="Production engineering",
            source_reference="BEP test fixture",
            authored_by="VSCS",
        ),
        metadata={"motion_class": "controlled"},
    )


def test_behaviour_profile_round_trips_complete_structured_contract(tmp_path: Path) -> None:
    database = _open_database(tmp_path)
    try:
        repository = BehaviourProfileRepository(database)
        created = repository.create(_profile(authority=BehaviourAuthority.APPROVED))
        restored = repository.get("bep-shp-dock", "1.0")

        assert restored == created
        assert restored is not None
        assert restored.parameters[0].name == "approach_speed"
        assert restored.preconditions[0].value is True
        assert restored.constraints[0].rule.startswith("Maintain docking-axis")
        assert restored.outcomes[0].resulting_state == "docked"
        assert restored.interactions[0].required_capabilities == ("accept docking",)
        assert restored.authority is BehaviourAuthority.APPROVED
        assert restored.provenance.source == "Production engineering"
        assert restored.metadata == {"motion_class": "controlled"}
    finally:
        database.close()


def test_repository_preserves_multiple_versions_and_rejects_duplicate_identity(
    tmp_path: Path,
) -> None:
    database = _open_database(tmp_path)
    try:
        repository = BehaviourProfileRepository(database)
        repository.create(_profile(version="1.0"))
        repository.create(_profile(version="2.0", authority=BehaviourAuthority.APPROVED))

        versions = repository.list_versions("BEP-SHP-DOCK")
        assert tuple(profile.version for profile in versions) == ("1.0", "2.0")

        with pytest.raises(BehaviourProfileRepositoryError, match="already exists"):
            repository.create(_profile(version="2.0"))
    finally:
        database.close()


def test_repository_filters_searches_updates_and_deletes_profiles(tmp_path: Path) -> None:
    database = _open_database(tmp_path)
    try:
        repository = BehaviourProfileRepository(database)
        repository.create(_profile())
        other = BehaviourProfile(
            profile_id="BEP-CHR-WALK",
            name="Character Walk",
            category=BehaviourCategory.LOCOMOTION,
            action="walk",
            applicable_asset_categories=(AssetCategory.CHARACTER,),
            authority=BehaviourAuthority.APPROVED,
            tags=("ground movement",),
        )
        repository.create(other)

        assert len(repository.list(query="docking")) == 1
        assert len(repository.list(category=BehaviourCategory.LOCOMOTION)) == 1
        assert len(repository.list(authority=BehaviourAuthority.APPROVED)) == 1
        assert len(repository.list(asset_category=AssetCategory.SHIP)) == 1
        character_profiles = repository.list(asset_category=AssetCategory.CHARACTER)
        assert character_profiles[0].profile_id == "BEP-CHR-WALK"

        changed = _profile().model_copy(
            update={
                "description": "Updated docking contract.",
                "authority": BehaviourAuthority.CANONICAL,
            }
        )
        updated = repository.update(changed)
        assert updated is not None
        assert updated.description == "Updated docking contract."
        assert updated.authority is BehaviourAuthority.CANONICAL

        assert repository.delete("BEP-SHP-DOCK", "1.0") is True
        assert repository.get("BEP-SHP-DOCK", "1.0") is None
        assert repository.delete("BEP-SHP-DOCK", "1.0") is False
    finally:
        database.close()


def test_repository_rejects_corrupt_persisted_structured_behaviour_data(tmp_path: Path) -> None:
    database = _open_database(tmp_path)
    try:
        repository = BehaviourProfileRepository(database)
        repository.create(_profile())
        with database.session() as session:
            session.execute(
                text(
                    "UPDATE behaviour_profiles SET parameters_json = :invalid "
                    "WHERE profile_id = :profile_id AND version = :version"
                ),
                {
                    "invalid": "{not-valid-json",
                    "profile_id": "BEP-SHP-DOCK",
                    "version": "1.0",
                },
            )

        with pytest.raises(BehaviourProfileRepositoryError, match="parameters"):
            repository.get("BEP-SHP-DOCK", "1.0")
    finally:
        database.close()
