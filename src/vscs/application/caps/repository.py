"""Database repository for Canonical Asset Profiles."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from vscs.domain.caps import CAPCreate, CAPStatus, CAPUpdate, CanonicalAssetProfile
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.database.models import CanonicalAssetProfileRecord


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
        statement: Select[tuple[CanonicalAssetProfileRecord]] = select(
            CanonicalAssetProfileRecord
        )
        if query.strip():
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    CanonicalAssetProfileRecord.asset_id.ilike(pattern),
                    CanonicalAssetProfileRecord.title.ilike(pattern),
                    CanonicalAssetProfileRecord.canonical_description.ilike(pattern),
                    CanonicalAssetProfileRecord.visual_identity.ilike(pattern),
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
                    if field_name == "status" and value is not None:
                        value = value.value
                    elif field_name == "reference_paths" and value is not None:
                        value = self._serialize_paths(value)
                    setattr(record, field_name, value)
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
    def _to_domain(record: CanonicalAssetProfileRecord) -> CanonicalAssetProfile:
        return CanonicalAssetProfile(
            id=record.id,
            asset_id=record.asset_id,
            title=record.title,
            version=record.version,
            status=CAPStatus(record.status),
            canonical_description=record.canonical_description,
            visual_identity=record.visual_identity,
            production_notes=record.production_notes,
            reference_paths=tuple(Path(path) for path in record.reference_paths.splitlines() if path),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
