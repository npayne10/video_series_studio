"""SQLite-backed repository for Behaviour Profiles."""

from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from vscs.domain.assets import AssetCategory
from vscs.domain.behaviours import (
    BehaviourAuthority,
    BehaviourCategory,
    BehaviourConstraint,
    BehaviourInteractionRequirement,
    BehaviourOutcome,
    BehaviourParameter,
    BehaviourPrecondition,
    BehaviourProfile,
    BehaviourProvenance,
)
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.database.models import BehaviourProfileRecord

_ASSET_CATEGORIES = TypeAdapter(tuple[AssetCategory, ...])
_STRINGS = TypeAdapter(tuple[str, ...])
_PARAMETERS = TypeAdapter(tuple[BehaviourParameter, ...])
_PRECONDITIONS = TypeAdapter(tuple[BehaviourPrecondition, ...])
_CONSTRAINTS = TypeAdapter(tuple[BehaviourConstraint, ...])
_OUTCOMES = TypeAdapter(tuple[BehaviourOutcome, ...])
_INTERACTIONS = TypeAdapter(tuple[BehaviourInteractionRequirement, ...])
_PROVENANCE = TypeAdapter(BehaviourProvenance)
_METADATA = TypeAdapter(dict[str, str])


class BehaviourProfileRepositoryError(RuntimeError):
    """Raised when Behaviour Profile persistence cannot complete safely."""


class BehaviourProfileRepository:
    """Persist versioned Behaviour Profiles in the active project database."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def create(self, profile: BehaviourProfile) -> BehaviourProfile:
        record = self._to_record(profile)
        try:
            with self.database.session() as session:
                session.add(record)
                session.flush()
                session.refresh(record)
                return self._to_domain(record)
        except IntegrityError as exc:
            raise BehaviourProfileRepositoryError(
                f"Behaviour Profile {profile.profile_id} version {profile.version} already exists"
            ) from exc
        except SQLAlchemyError as exc:
            raise BehaviourProfileRepositoryError(
                f"Unable to create Behaviour Profile {profile.profile_id}: {exc}"
            ) from exc

    def get(self, profile_id: str, version: str) -> BehaviourProfile | None:
        normalized_id = profile_id.strip().upper()
        try:
            with self.database.session() as session:
                record = session.scalar(
                    select(BehaviourProfileRecord).where(
                        BehaviourProfileRecord.profile_id == normalized_id,
                        BehaviourProfileRecord.version == version.strip(),
                    )
                )
                return None if record is None else self._to_domain(record)
        except SQLAlchemyError as exc:
            raise BehaviourProfileRepositoryError(
                f"Unable to read Behaviour Profile {normalized_id} version {version}: {exc}"
            ) from exc

    def list(
        self,
        *,
        query: str = "",
        category: BehaviourCategory | None = None,
        authority: BehaviourAuthority | None = None,
        asset_category: AssetCategory | None = None,
    ) -> tuple[BehaviourProfile, ...]:
        statement: Select[tuple[BehaviourProfileRecord]] = select(BehaviourProfileRecord)
        if query.strip():
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    BehaviourProfileRecord.profile_id.ilike(pattern),
                    BehaviourProfileRecord.name.ilike(pattern),
                    BehaviourProfileRecord.description.ilike(pattern),
                    BehaviourProfileRecord.action.ilike(pattern),
                    BehaviourProfileRecord.tags_json.ilike(pattern),
                )
            )
        if category is not None:
            statement = statement.where(BehaviourProfileRecord.category == category.value)
        if authority is not None:
            statement = statement.where(BehaviourProfileRecord.authority == authority.value)
        statement = statement.order_by(
            BehaviourProfileRecord.profile_id,
            BehaviourProfileRecord.version,
        )
        try:
            with self.database.session() as session:
                profiles = tuple(self._to_domain(record) for record in session.scalars(statement))
        except SQLAlchemyError as exc:
            raise BehaviourProfileRepositoryError(
                f"Unable to list Behaviour Profiles: {exc}"
            ) from exc
        if asset_category is None:
            return profiles
        return tuple(
            profile
            for profile in profiles
            if asset_category in profile.applicable_asset_categories
        )

    def list_versions(self, profile_id: str) -> tuple[BehaviourProfile, ...]:
        normalized_id = profile_id.strip().upper()
        statement = (
            select(BehaviourProfileRecord)
            .where(BehaviourProfileRecord.profile_id == normalized_id)
            .order_by(BehaviourProfileRecord.version)
        )
        try:
            with self.database.session() as session:
                return tuple(self._to_domain(record) for record in session.scalars(statement))
        except SQLAlchemyError as exc:
            raise BehaviourProfileRepositoryError(
                f"Unable to list Behaviour Profile versions for {normalized_id}: {exc}"
            ) from exc

    def update(self, profile: BehaviourProfile) -> BehaviourProfile | None:
        try:
            with self.database.session() as session:
                record = session.scalar(
                    select(BehaviourProfileRecord).where(
                        BehaviourProfileRecord.profile_id == profile.profile_id,
                        BehaviourProfileRecord.version == profile.version,
                    )
                )
                if record is None:
                    return None
                self._apply_profile(record, profile)
                session.flush()
                session.refresh(record)
                return self._to_domain(record)
        except SQLAlchemyError as exc:
            raise BehaviourProfileRepositoryError(
                f"Unable to update Behaviour Profile {profile.profile_id}: {exc}"
            ) from exc

    def delete(self, profile_id: str, version: str) -> bool:
        normalized_id = profile_id.strip().upper()
        try:
            with self.database.session() as session:
                record = session.scalar(
                    select(BehaviourProfileRecord).where(
                        BehaviourProfileRecord.profile_id == normalized_id,
                        BehaviourProfileRecord.version == version.strip(),
                    )
                )
                if record is None:
                    return False
                session.delete(record)
                session.flush()
                return True
        except SQLAlchemyError as exc:
            raise BehaviourProfileRepositoryError(
                f"Unable to delete Behaviour Profile {normalized_id} version {version}: {exc}"
            ) from exc

    @classmethod
    def _to_record(cls, profile: BehaviourProfile) -> BehaviourProfileRecord:
        record = BehaviourProfileRecord(
            profile_id=profile.profile_id,
            version=profile.version,
        )
        cls._apply_profile(record, profile)
        return record

    @classmethod
    def _apply_profile(cls, record: BehaviourProfileRecord, profile: BehaviourProfile) -> None:
        record.schema_version = profile.schema_version
        record.name = profile.name
        record.description = profile.description
        record.category = profile.category.value
        record.action = profile.action
        record.applicable_asset_categories_json = cls._serialize_json(
            tuple(category.value for category in profile.applicable_asset_categories)
        )
        record.aliases_json = cls._serialize_json(profile.aliases)
        record.parameters_json = cls._serialize_models(profile.parameters)
        record.preconditions_json = cls._serialize_models(profile.preconditions)
        record.constraints_json = cls._serialize_models(profile.constraints)
        record.outcomes_json = cls._serialize_models(profile.outcomes)
        record.interactions_json = cls._serialize_models(profile.interactions)
        record.tags_json = cls._serialize_json(profile.tags)
        record.authority = profile.authority.value
        record.provenance_json = cls._serialize_model(profile.provenance)
        record.metadata_json = cls._serialize_json(profile.metadata)

    @staticmethod
    def _serialize_models(values: tuple[Any, ...]) -> str:
        return json.dumps([value.model_dump(mode="json") for value in values], sort_keys=True)

    @staticmethod
    def _serialize_model(value: Any) -> str:
        return json.dumps(value.model_dump(mode="json"), sort_keys=True)

    @staticmethod
    def _serialize_json(value: object) -> str:
        return json.dumps(value, sort_keys=True)

    @staticmethod
    def _decode(raw: str, adapter: TypeAdapter[Any], label: str) -> Any:
        try:
            return adapter.validate_python(json.loads(raw))
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise BehaviourProfileRepositoryError(
                f"Persisted Behaviour Profile {label} is invalid"
            ) from exc

    @classmethod
    def _to_domain(cls, record: BehaviourProfileRecord) -> BehaviourProfile:
        return BehaviourProfile(
            schema_version=record.schema_version,
            profile_id=record.profile_id,
            name=record.name,
            version=record.version,
            description=record.description,
            category=BehaviourCategory(record.category),
            action=record.action,
            applicable_asset_categories=cls._decode(
                record.applicable_asset_categories_json,
                _ASSET_CATEGORIES,
                "asset categories",
            ),
            aliases=cls._decode(record.aliases_json, _STRINGS, "aliases"),
            parameters=cls._decode(record.parameters_json, _PARAMETERS, "parameters"),
            preconditions=cls._decode(
                record.preconditions_json,
                _PRECONDITIONS,
                "preconditions",
            ),
            constraints=cls._decode(record.constraints_json, _CONSTRAINTS, "constraints"),
            outcomes=cls._decode(record.outcomes_json, _OUTCOMES, "outcomes"),
            interactions=cls._decode(
                record.interactions_json,
                _INTERACTIONS,
                "interactions",
            ),
            tags=cls._decode(record.tags_json, _STRINGS, "tags"),
            authority=BehaviourAuthority(record.authority),
            provenance=cls._decode(record.provenance_json, _PROVENANCE, "provenance"),
            metadata=cls._decode(record.metadata_json, _METADATA, "metadata"),
        )
