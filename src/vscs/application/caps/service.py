"""Application service for Canonical Asset Profiles."""

from __future__ import annotations

from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.caps.repository import CAPRepository, CAPRepositoryError
from vscs.domain.caps import CanonicalAssetProfile, CAPCreate, CAPStatus, CAPUpdate
from vscs.infrastructure.logging import LoggingService


class CAPError(RuntimeError):
    """Base exception for CAP management failures."""


class CAPNotFoundError(CAPError):
    """Raised when a requested CAP does not exist."""


class CAPAlreadyExistsError(CAPError):
    """Raised when an asset already has a CAP."""


class CAPAssetNotFoundError(CAPError):
    """Raised when a CAP references an unregistered asset."""


class InvalidCAPReferencePathError(CAPError):
    """Raised when a CAP reference file is outside the project."""


class CAPService:
    """Coordinate CAP validation, persistence, and asset linkage."""

    def __init__(self, assets: AssetService, repository: CAPRepository) -> None:
        self.assets = assets
        self.repository = repository
        self._logger = LoggingService.get_logger("caps")

    def create(self, profile: CAPCreate) -> CanonicalAssetProfile:
        self._require_asset(profile.asset_id)
        if self.repository.get(profile.asset_id) is not None:
            raise CAPAlreadyExistsError(f"CAP already exists for asset: {profile.asset_id}")
        normalized = profile.model_copy(
            update={"reference_paths": self._normalize_paths(profile.reference_paths)}
        )
        try:
            created = self.repository.create(normalized)
        except CAPRepositoryError as exc:
            raise CAPError(str(exc)) from exc
        self._logger.info("CAP created: %s", created.asset_id)
        return created

    def get(self, asset_id: str) -> CanonicalAssetProfile:
        normalized_id = asset_id.strip().upper()
        try:
            profile = self.repository.get(normalized_id)
        except CAPRepositoryError as exc:
            raise CAPError(str(exc)) from exc
        if profile is None:
            raise CAPNotFoundError(f"CAP not found for asset: {normalized_id}")
        return profile

    def list(
        self, *, query: str = "", status: CAPStatus | None = None
    ) -> tuple[CanonicalAssetProfile, ...]:
        self.assets.list()
        try:
            return self.repository.list(query=query, status=status)
        except CAPRepositoryError as exc:
            raise CAPError(str(exc)) from exc

    def update(self, asset_id: str, changes: CAPUpdate) -> CanonicalAssetProfile:
        normalized_id = asset_id.strip().upper()
        values = changes.model_dump(exclude_unset=True)
        if "reference_paths" in values and changes.reference_paths is not None:
            values["reference_paths"] = self._normalize_paths(changes.reference_paths)
        normalized = CAPUpdate.model_validate(values)
        try:
            updated = self.repository.update(normalized_id, normalized)
        except CAPRepositoryError as exc:
            raise CAPError(str(exc)) from exc
        if updated is None:
            raise CAPNotFoundError(f"CAP not found for asset: {normalized_id}")
        self._logger.info("CAP updated: %s", normalized_id)
        return updated

    def delete(self, asset_id: str) -> None:
        normalized_id = asset_id.strip().upper()
        try:
            deleted = self.repository.delete(normalized_id)
        except CAPRepositoryError as exc:
            raise CAPError(str(exc)) from exc
        if not deleted:
            raise CAPNotFoundError(f"CAP not found for asset: {normalized_id}")
        self._logger.info("CAP deleted: %s", normalized_id)

    def available_assets(self) -> tuple[tuple[str, str], ...]:
        """Return registered assets that do not yet have a CAP."""
        existing = {profile.asset_id for profile in self.list()}
        return tuple(
            (asset.asset_id, asset.name)
            for asset in self.assets.list()
            if asset.asset_id not in existing
        )

    def _require_asset(self, asset_id: str) -> None:
        try:
            self.assets.get(asset_id)
        except Exception as exc:
            raise CAPAssetNotFoundError(
                f"Register asset {asset_id} before creating its CAP"
            ) from exc

    def _normalize_paths(self, paths: tuple[Path, ...]) -> tuple[Path, ...]:
        project_directory = self.assets.projects.project_directory
        if project_directory is None:
            raise CAPError("Open a VSCS project before managing CAPs")
        root = project_directory.resolve(strict=False)
        normalized: list[Path] = []
        for path in paths:
            resolved = (
                path.expanduser().resolve(strict=False)
                if path.is_absolute()
                else (root / path).resolve(strict=False)
            )
            try:
                relative = resolved.relative_to(root)
            except ValueError as exc:
                raise InvalidCAPReferencePathError(
                    f"CAP reference files must be inside the active project: {resolved}"
                ) from exc
            if relative not in normalized:
                normalized.append(relative)
        return tuple(normalized)
