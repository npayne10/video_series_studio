"""Database repository for production assets."""

from __future__ import annotations

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from vscs.domain.assets import Asset, AssetCategory, AssetCreate, AssetStatus, AssetUpdate
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.database.models import AssetRecord


class AssetRepositoryError(RuntimeError):
    """Raised when asset persistence fails."""


class AssetRepository:
    """Persist and query project assets through the active database."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def create(self, asset: AssetCreate) -> Asset:
        """Create a new asset record."""
        record = AssetRecord(
            asset_id=asset.asset_id,
            name=asset.name,
            category=asset.category.value,
            description=asset.description,
            status=asset.status.value,
            file_path=str(asset.file_path) if asset.file_path is not None else None,
            tags=self._serialize_tags(asset.tags),
        )
        try:
            with self.database.session() as session:
                session.add(record)
                session.flush()
                session.refresh(record)
                return self._to_domain(record)
        except (IntegrityError, SQLAlchemyError) as exc:
            raise AssetRepositoryError(f"Unable to create asset {asset.asset_id}: {exc}") from exc

    def get(self, asset_id: str) -> Asset | None:
        """Return one asset by its canonical identifier."""
        try:
            with self.database.session() as session:
                record = session.scalar(select(AssetRecord).where(AssetRecord.asset_id == asset_id))
                return None if record is None else self._to_domain(record)
        except SQLAlchemyError as exc:
            raise AssetRepositoryError(f"Unable to read asset {asset_id}: {exc}") from exc

    def list(
        self,
        *,
        query: str = "",
        category: AssetCategory | None = None,
        status: AssetStatus | None = None,
    ) -> tuple[Asset, ...]:
        """Return assets matching optional text and classification filters."""
        statement: Select[tuple[AssetRecord]] = select(AssetRecord)
        if query.strip():
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    AssetRecord.asset_id.ilike(pattern),
                    AssetRecord.name.ilike(pattern),
                    AssetRecord.description.ilike(pattern),
                    AssetRecord.tags.ilike(pattern),
                )
            )
        if category is not None:
            statement = statement.where(AssetRecord.category == category.value)
        if status is not None:
            statement = statement.where(AssetRecord.status == status.value)
        statement = statement.order_by(AssetRecord.category, AssetRecord.asset_id)
        try:
            with self.database.session() as session:
                return tuple(self._to_domain(record) for record in session.scalars(statement))
        except SQLAlchemyError as exc:
            raise AssetRepositoryError(f"Unable to list assets: {exc}") from exc

    def update(self, asset_id: str, changes: AssetUpdate) -> Asset | None:
        """Apply a partial update and return the updated asset."""
        try:
            with self.database.session() as session:
                record = session.scalar(select(AssetRecord).where(AssetRecord.asset_id == asset_id))
                if record is None:
                    return None
                values = changes.model_dump(exclude_unset=True)
                for field_name, value in values.items():
                    if field_name in {"category", "status"} and value is not None:
                        value = value.value
                    elif field_name == "file_path" and value is not None:
                        value = str(value)
                    elif field_name == "tags" and value is not None:
                        value = self._serialize_tags(value)
                    setattr(record, field_name, value)
                session.flush()
                session.refresh(record)
                return self._to_domain(record)
        except SQLAlchemyError as exc:
            raise AssetRepositoryError(f"Unable to update asset {asset_id}: {exc}") from exc

    def delete(self, asset_id: str) -> bool:
        """Delete an asset by identifier and report whether it existed."""
        try:
            with self.database.session() as session:
                result = session.execute(delete(AssetRecord).where(AssetRecord.asset_id == asset_id))
                return bool(result.rowcount)
        except SQLAlchemyError as exc:
            raise AssetRepositoryError(f"Unable to delete asset {asset_id}: {exc}") from exc

    def count(self) -> int:
        """Return the number of assets in the active project."""
        try:
            with self.database.session() as session:
                return session.scalar(select(func.count()).select_from(AssetRecord)) or 0
        except SQLAlchemyError as exc:
            raise AssetRepositoryError(f"Unable to count assets: {exc}") from exc

    @staticmethod
    def _serialize_tags(tags: tuple[str, ...]) -> str:
        return "\n".join(tags)

    @staticmethod
    def _to_domain(record: AssetRecord) -> Asset:
        return Asset(
            id=record.id,
            asset_id=record.asset_id,
            name=record.name,
            category=AssetCategory(record.category),
            description=record.description,
            status=AssetStatus(record.status),
            file_path=record.file_path,
            tags=tuple(tag for tag in record.tags.splitlines() if tag),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
