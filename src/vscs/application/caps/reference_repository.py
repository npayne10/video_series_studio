"""Database repository for structured CAP canonical references."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from vscs.domain.caps import (
    CanonicalReference,
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CanonicalReferenceUpdate,
)
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.database.models import CanonicalReferenceRecord


class CanonicalReferenceRepositoryError(RuntimeError):
    """Raised when canonical reference persistence fails."""


class CanonicalReferenceRepository:
    """Persist and query structured canonical references."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def create(self, reference: CanonicalReferenceCreate) -> CanonicalReference:
        record = CanonicalReferenceRecord(
            cap_id=reference.cap_id,
            reference_type=reference.reference_type.value,
            role=reference.role.value,
            title=reference.title,
            file_path=str(reference.file_path),
            description=reference.description,
            notes=reference.notes,
            version=reference.version,
            status=reference.status.value,
            approved_by=reference.approved_by,
            approved_at=reference.approved_at,
            locked=reference.locked,
        )
        try:
            with self.database.session() as session:
                session.add(record)
                session.flush()
                session.refresh(record)
                return self._to_domain(record)
        except (IntegrityError, SQLAlchemyError) as exc:
            raise CanonicalReferenceRepositoryError(
                f"Unable to create canonical reference for CAP {reference.cap_id}: {exc}"
            ) from exc

    def get(self, reference_id: int) -> CanonicalReference | None:
        try:
            with self.database.session() as session:
                record = session.get(CanonicalReferenceRecord, reference_id)
                return None if record is None else self._to_domain(record)
        except SQLAlchemyError as exc:
            raise CanonicalReferenceRepositoryError(
                f"Unable to read canonical reference {reference_id}: {exc}"
            ) from exc

    def list_for_cap(
        self,
        cap_id: int,
        *,
        reference_type: CanonicalReferenceType | None = None,
        status: CanonicalReferenceStatus | None = None,
    ) -> tuple[CanonicalReference, ...]:
        statement: Select[tuple[CanonicalReferenceRecord]] = select(CanonicalReferenceRecord).where(
            CanonicalReferenceRecord.cap_id == cap_id
        )
        if reference_type is not None:
            statement = statement.where(
                CanonicalReferenceRecord.reference_type == reference_type.value
            )
        if status is not None:
            statement = statement.where(CanonicalReferenceRecord.status == status.value)
        statement = statement.order_by(
            CanonicalReferenceRecord.reference_type,
            CanonicalReferenceRecord.role,
            CanonicalReferenceRecord.title,
        )
        try:
            with self.database.session() as session:
                return tuple(self._to_domain(record) for record in session.scalars(statement))
        except SQLAlchemyError as exc:
            raise CanonicalReferenceRepositoryError(
                f"Unable to list canonical references for CAP {cap_id}: {exc}"
            ) from exc

    def update(
        self, reference_id: int, changes: CanonicalReferenceUpdate
    ) -> CanonicalReference | None:
        try:
            with self.database.session() as session:
                record = session.get(CanonicalReferenceRecord, reference_id)
                if record is None:
                    return None
                for field_name, value in changes.model_dump(exclude_unset=True).items():
                    if field_name in {"reference_type", "role", "status"} and value is not None:
                        value = value.value
                    elif field_name == "file_path" and value is not None:
                        value = str(value)
                    setattr(record, field_name, value)
                session.flush()
                session.refresh(record)
                return self._to_domain(record)
        except (IntegrityError, SQLAlchemyError) as exc:
            raise CanonicalReferenceRepositoryError(
                f"Unable to update canonical reference {reference_id}: {exc}"
            ) from exc

    def delete(self, reference_id: int) -> bool:
        try:
            with self.database.session() as session:
                record = session.get(CanonicalReferenceRecord, reference_id)
                if record is None:
                    return False
                session.delete(record)
                session.flush()
                return True
        except SQLAlchemyError as exc:
            raise CanonicalReferenceRepositoryError(
                f"Unable to delete canonical reference {reference_id}: {exc}"
            ) from exc

    @staticmethod
    def _to_domain(record: CanonicalReferenceRecord) -> CanonicalReference:
        return CanonicalReference(
            id=record.id,
            cap_id=record.cap_id,
            reference_type=CanonicalReferenceType(record.reference_type),
            role=CanonicalReferenceRole(record.role),
            title=record.title,
            file_path=Path(record.file_path),
            description=record.description,
            notes=record.notes,
            version=record.version,
            status=CanonicalReferenceStatus(record.status),
            approved_by=record.approved_by,
            approved_at=record.approved_at,
            locked=record.locked,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
