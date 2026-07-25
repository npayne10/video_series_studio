"""Application service for structured CAP canonical references."""

from __future__ import annotations

from pathlib import Path

from vscs.application.caps.reference_repository import (
    CanonicalReferenceRepository,
    CanonicalReferenceRepositoryError,
)
from vscs.application.caps.service import CAPService
from vscs.domain.caps import (
    CanonicalReference,
    CanonicalReferenceCreate,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CanonicalReferenceUpdate,
)
from vscs.infrastructure.logging import LoggingService


class CanonicalReferenceError(RuntimeError):
    """Base exception for canonical reference management failures."""


class CanonicalReferenceNotFoundError(CanonicalReferenceError):
    """Raised when a requested canonical reference does not exist."""


class InvalidCanonicalReferencePathError(CanonicalReferenceError):
    """Raised when a canonical reference is outside the active project."""


class CanonicalReferenceService:
    """Coordinate canonical reference validation and persistence."""

    def __init__(
        self,
        caps: CAPService,
        repository: CanonicalReferenceRepository,
    ) -> None:
        self.caps = caps
        self.repository = repository
        self._logger = LoggingService.get_logger("canonical_references")

    def create(
        self,
        asset_id: str,
        reference: CanonicalReferenceCreate,
    ) -> CanonicalReference:
        cap = self.caps.get(asset_id)
        normalized = reference.model_copy(
            update={
                "cap_id": cap.id,
                "file_path": self._normalize_path(reference.file_path),
            }
        )
        try:
            created = self.repository.create(normalized)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        self._logger.info(
            "Canonical reference created: CAP %s, reference %s",
            cap.asset_id,
            created.id,
        )
        return created

    def get(self, reference_id: int) -> CanonicalReference:
        self._require_project()
        try:
            reference = self.repository.get(reference_id)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        if reference is None:
            raise CanonicalReferenceNotFoundError(
                f"Canonical reference not found: {reference_id}"
            )
        return reference

    def list_for_cap(
        self,
        asset_id: str,
        *,
        reference_type: CanonicalReferenceType | None = None,
        status: CanonicalReferenceStatus | None = None,
    ) -> tuple[CanonicalReference, ...]:
        cap = self.caps.get(asset_id)
        try:
            return self.repository.list_for_cap(
                cap.id,
                reference_type=reference_type,
                status=status,
            )
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc

    def update(
        self,
        reference_id: int,
        changes: CanonicalReferenceUpdate,
    ) -> CanonicalReference:
        self._require_project()
        values = changes.model_dump(exclude_unset=True)
        if "file_path" in values and changes.file_path is not None:
            values["file_path"] = self._normalize_path(changes.file_path)
        normalized = CanonicalReferenceUpdate.model_validate(values)
        try:
            updated = self.repository.update(reference_id, normalized)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        if updated is None:
            raise CanonicalReferenceNotFoundError(
                f"Canonical reference not found: {reference_id}"
            )
        self._logger.info("Canonical reference updated: %s", reference_id)
        return updated

    def delete(self, reference_id: int) -> None:
        self._require_project()
        try:
            deleted = self.repository.delete(reference_id)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        if not deleted:
            raise CanonicalReferenceNotFoundError(
                f"Canonical reference not found: {reference_id}"
            )
        self._logger.info("Canonical reference deleted: %s", reference_id)

    def _require_project(self) -> Path:
        project_directory = self.caps.assets.projects.project_directory
        if not self.caps.assets.projects.is_project_open or project_directory is None:
            raise CanonicalReferenceError(
                "Open a VSCS project before managing canonical references"
            )
        return project_directory

    def _normalize_path(self, path: Path) -> Path:
        root = self._require_project().resolve(strict=False)
        resolved = (
            path.expanduser().resolve(strict=False)
            if path.is_absolute()
            else (root / path).resolve(strict=False)
        )
        try:
            return resolved.relative_to(root)
        except ValueError as exc:
            raise InvalidCanonicalReferencePathError(
                f"Canonical reference files must be inside the active project: {resolved}"
            ) from exc
