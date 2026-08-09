"""Database repository for Canonical Asset Profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from vscs.domain.caps import CanonicalAssetProfile, CAPCreate, CAPStatus, CAPUpdate
from vscs.domain.caps.structured_knowledge import (
    PersistedCanonicalConstraint,
    PersistedCanonicalFact,
    PersistedFunctionalCapability,
)
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.database.models import CanonicalAssetProfileRecord

_FACTS = TypeAdapter(tuple[PersistedCanonicalFact, ...])
_CAPABILITIES = TypeAdapter(tuple[PersistedFunctionalCapability, ...])
_CONSTRAINTS = TypeAdapter(tuple[PersistedCanonicalConstraint, ...])
_STRINGS = TypeAdapter(tuple[str, ...])
_METADATA = TypeAdapter(dict[str, str])


class CAPRepositoryError(RuntimeError):
    """Raised when CAP persistence fails."""


class CAPRepository:
    """Persist and query CAP records through the active project database."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def create(self, profile: CAPCreate) -> CanonicalAssetProfile:
        record = CanonicalAssetProfileRecord(
            asset_id=profile.asset_id,
            title=profile.title,
            version=profile.version,
            status=profile.status.value,
            canonical_description=profile.canonical_description,
            visual_identity=profile.visual_identity,
            production_notes=profile.production_notes,
            reference_paths=self._serialize_paths(profile.reference_paths),
            structured_schema_version=profile.structured_schema_version,
            facts_json=self._serialize_models(profile.facts),
            functional_identity_json=self._serialize_models(profile.functional_identity),
            constraints_json=self._serialize_models(profile.constraints),
            semantic_tags_json=self._serialize_json(profile.semantic_tags),
            production_classifications_json=self._serialize_json(
                profile.production_classifications
            ),
            behaviour_references_json=self._serialize_json(profile.behaviour_references),
            production_metadata_json=self._serialize_json(profile.production_metadata),
        )
        try:
            with self.database.session() as session:
                session.add(record)
                session.flush()
                session.refresh(record)
                return self._to_domain(record)
        except (IntegrityError, SQLAlchemyError) as exc:
            raise CAPRepositoryError(f"Unable to create CAP for {profile.asset_id}: {exc}") from exc

    def get(self, asset_id: str) -> CanonicalAssetProfile | None:
        try:
            with self.database.session() as session:
                record = session.scalar(
                    select(CanonicalAssetProfileRecord).where(
                        CanonicalAssetProfileRecord.asset_id == asset_id
                    )
                )
                return None if record is None else self._to_domain(record)
        except SQLAlchemyError as exc:
            raise CAPRepositoryError(f"Unable to read CAP for {asset_id}: {exc}") from exc

    def list(
        self, *, query: str = "", status: CAPStatus | None = None
    ) -> tuple[CanonicalAssetProfile, ...]:
        statement: Select[tuple[CanonicalAssetProfileRecord]] = select(CanonicalAssetProfileRecord)
        if query.strip():
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    CanonicalAssetProfileRecord.asset_id.ilike(pattern),
                    CanonicalAssetProfileRecord.title.ilike(pattern),
                    CanonicalAssetProfileRecord.canonical_description.ilike(pattern),
                    CanonicalAssetProfileRecord.visual_identity.ilike(pattern),
                    CanonicalAssetProfileRecord.facts_json.ilike(pattern),
                    CanonicalAssetProfileRecord.functional_identity_json.ilike(pattern),
                    CanonicalAssetProfileRecord.constraints_json.ilike(pattern),
                    CanonicalAssetProfileRecord.semantic_tags_json.ilike(pattern),
                )
            )
        if status is not None:
            statement = statement.where(CanonicalAssetProfileRecord.status == status.value)
        statement = statement.order_by(CanonicalAssetProfileRecord.asset_id)
        try:
            with self.database.session() as session:
                return tuple(self._to_domain(record) for record in session.scalars(statement))
        except SQLAlchemyError as exc:
            raise CAPRepositoryError(f"Unable to list CAPs: {exc}") from exc

    def update(self, asset_id: str, changes: CAPUpdate) -> CanonicalAssetProfile | None:
        try:
            with self.database.session() as session:
                record = session.scalar(
                    select(CanonicalAssetProfileRecord).where(
                        CanonicalAssetProfileRecord.asset_id == asset_id
                    )
                )
                if record is None:
                    return None
                for field_name, value in changes.model_dump(exclude_unset=True).items():
                    target_name = field_name
                    if field_name == "status" and value is not None:
                        value = value.value
                    elif field_name == "reference_paths" and value is not None:
                        value = self._serialize_paths(value)
                    elif field_name in {"facts", "functional_identity", "constraints"}:
                        target_name = f"{field_name}_json"
                        model_values = getattr(changes, field_name)
                        value = self._serialize_models(model_values or ())
                    elif field_name in {
                        "semantic_tags",
                        "production_classifications",
                        "behaviour_references",
                        "production_metadata",
                    }:
                        target_name = f"{field_name}_json"
                        value = self._serialize_json(getattr(changes, field_name) or ())
                        if field_name == "production_metadata":
                            value = self._serialize_json(getattr(changes, field_name) or {})
                    setattr(record, target_name, value)
                session.flush()
                session.refresh(record)
                return self._to_domain(record)
        except SQLAlchemyError as exc:
            raise CAPRepositoryError(f"Unable to update CAP for {asset_id}: {exc}") from exc

    def delete(self, asset_id: str) -> bool:
        try:
            with self.database.session() as session:
                record = session.scalar(
                    select(CanonicalAssetProfileRecord).where(
                        CanonicalAssetProfileRecord.asset_id == asset_id
                    )
                )
                if record is None:
                    return False
                session.delete(record)
                session.flush()
                return True
        except SQLAlchemyError as exc:
            raise CAPRepositoryError(f"Unable to delete CAP for {asset_id}: {exc}") from exc

    @staticmethod
    def _serialize_paths(paths: tuple[Path, ...]) -> str:
        return "\n".join(str(path) for path in paths)

    @staticmethod
    def _serialize_models(values: tuple[Any, ...]) -> str:
        return json.dumps([value.model_dump(mode="json") for value in values], sort_keys=True)

    @staticmethod
    def _serialize_json(value: object) -> str:
        return json.dumps(value, sort_keys=True)

    @staticmethod
    def _decode(raw: str, adapter: TypeAdapter[Any], default: Any) -> Any:
        try:
            return adapter.validate_python(json.loads(raw or "null"))
        except (json.JSONDecodeError, ValidationError, TypeError):
            return default

    @classmethod
    def _to_domain(cls, record: CanonicalAssetProfileRecord) -> CanonicalAssetProfile:
        return CanonicalAssetProfile(
            id=record.id,
            asset_id=record.asset_id,
            title=record.title,
            version=record.version,
            status=CAPStatus(record.status),
            canonical_description=record.canonical_description,
            visual_identity=record.visual_identity,
            production_notes=record.production_notes,
            reference_paths=tuple(
                Path(path) for path in record.reference_paths.splitlines() if path
            ),
            structured_schema_version=record.structured_schema_version,
            facts=cls._decode(record.facts_json, _FACTS, ()),
            functional_identity=cls._decode(record.functional_identity_json, _CAPABILITIES, ()),
            constraints=cls._decode(record.constraints_json, _CONSTRAINTS, ()),
            semantic_tags=cls._decode(record.semantic_tags_json, _STRINGS, ()),
            production_classifications=cls._decode(
                record.production_classifications_json, _STRINGS, ()
            ),
            behaviour_references=cls._decode(record.behaviour_references_json, _STRINGS, ()),
            production_metadata=cls._decode(record.production_metadata_json, _METADATA, {}),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
