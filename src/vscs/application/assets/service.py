"""Application service for managing project assets."""

from __future__ import annotations

from pathlib import Path

from vscs.application.assets.repository import AssetRepository, AssetRepositoryError
from vscs.application.projects import ProjectService
from vscs.domain.assets import Asset, AssetCategory, AssetCreate, AssetStatus, AssetUpdate
from vscs.infrastructure.logging import LoggingService


class AssetError(RuntimeError):
    """Base exception for asset management failures."""


class AssetNotFoundError(AssetError):
    """Raised when a requested asset does not exist."""


class AssetAlreadyExistsError(AssetError):
    """Raised when an asset identifier is already registered."""


class AssetProjectNotOpenError(AssetError):
    """Raised when an asset operation requires an active project."""


class InvalidAssetPathError(AssetError):
    """Raised when a file path points outside the active project."""


class AssetService:
    """Coordinate validation, persistence, and project-scoped asset paths."""

    def __init__(self, projects: ProjectService, repository: AssetRepository) -> None:
        self.projects = projects
        self.repository = repository
        self._logger = LoggingService.get_logger("assets")

    def create(self, asset: AssetCreate) -> Asset:
        """Register a new production asset in the active project."""
        self._require_project()
        if self.repository.get(asset.asset_id) is not None:
            raise AssetAlreadyExistsError(f"Asset already exists: {asset.asset_id}")
        normalized = asset.model_copy(update={"file_path": self._normalize_path(asset.file_path)})
        try:
            created = self.repository.create(normalized)
        except AssetRepositoryError as exc:
            raise AssetError(str(exc)) from exc
        self._logger.info("Asset created: %s", created.asset_id)
        return created

    def get(self, asset_id: str) -> Asset:
        """Return an asset by identifier."""
        self._require_project()
        normalized_id = asset_id.strip().upper()
        try:
            asset = self.repository.get(normalized_id)
        except AssetRepositoryError as exc:
            raise AssetError(str(exc)) from exc
        if asset is None:
            raise AssetNotFoundError(f"Asset not found: {normalized_id}")
        return asset

    def list(
        self,
        *,
        query: str = "",
        category: AssetCategory | None = None,
        status: AssetStatus | None = None,
    ) -> tuple[Asset, ...]:
        """List assets using optional text, category, and status filters."""
        self._require_project()
        try:
            return self.repository.list(query=query, category=category, status=status)
        except AssetRepositoryError as exc:
            raise AssetError(str(exc)) from exc

    def update(self, asset_id: str, changes: AssetUpdate) -> Asset:
        """Update an existing asset."""
        self._require_project()
        normalized_id = asset_id.strip().upper()
        update_values = changes.model_dump(exclude_unset=True)
        if "file_path" in update_values:
            update_values["file_path"] = self._normalize_path(changes.file_path)
        normalized_changes = AssetUpdate.model_validate(update_values)
        try:
            updated = self.repository.update(normalized_id, normalized_changes)
        except AssetRepositoryError as exc:
            raise AssetError(str(exc)) from exc
        if updated is None:
            raise AssetNotFoundError(f"Asset not found: {normalized_id}")
        self._logger.info("Asset updated: %s", normalized_id)
        return updated

    def delete(self, asset_id: str) -> None:
        """Remove an asset record without deleting its source media file."""
        self._require_project()
        normalized_id = asset_id.strip().upper()
        try:
            deleted = self.repository.delete(normalized_id)
        except AssetRepositoryError as exc:
            raise AssetError(str(exc)) from exc
        if not deleted:
            raise AssetNotFoundError(f"Asset not found: {normalized_id}")
        self._logger.info("Asset deleted: %s", normalized_id)

    def count(self) -> int:
        """Return the active project's asset count."""
        self._require_project()
        try:
            return self.repository.count()
        except AssetRepositoryError as exc:
            raise AssetError(str(exc)) from exc

    def absolute_file_path(self, asset: Asset) -> Path | None:
        """Resolve an asset's stored relative path against the active project."""
        project_directory = self._require_project()
        if asset.file_path is None:
            return None
        return (project_directory / asset.file_path).resolve(strict=False)

    def _normalize_path(self, file_path: Path | None) -> Path | None:
        if file_path is None:
            return None
        project_directory = self._require_project()
        resolved = (
            file_path.expanduser().resolve(strict=False)
            if file_path.is_absolute()
            else (project_directory / file_path).resolve(strict=False)
        )
        try:
            relative = resolved.relative_to(project_directory)
        except ValueError as exc:
            raise InvalidAssetPathError(
                f"Asset files must be inside the active project: {resolved}"
            ) from exc
        return relative

    def _require_project(self) -> Path:
        if not self.projects.is_project_open or self.projects.project_directory is None:
            raise AssetProjectNotOpenError("Open a VSCS project before managing assets")
        return self.projects.project_directory.resolve(strict=False)
