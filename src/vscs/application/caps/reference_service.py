"""Application service for structured CAP canonical references."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from vscs.application.caps.reference_repository import (
    CanonicalReferenceRepository,
    CanonicalReferenceRepositoryError,
)
from vscs.application.caps.service import CAPService
from vscs.domain.caps import (
    CanonicalReference,
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
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


class CanonicalReferenceLockedError(CanonicalReferenceError):
    """Raised when normal editing is attempted on an approved reference."""


class InvalidCanonicalReferenceTransitionError(CanonicalReferenceError):
    """Raised when a lifecycle transition is not permitted."""


class CanonicalReferenceService:
    """Coordinate canonical reference validation, workflow, and persistence."""

    def __init__(self, caps: CAPService, repository: CanonicalReferenceRepository) -> None:
        self.caps = caps
        self.repository = repository
        self._logger = LoggingService.get_logger("canonical_references")

    def create(self, asset_id: str, reference: CanonicalReferenceCreate) -> CanonicalReference:
        cap = self.caps.get(asset_id)
        normalized = reference.model_copy(update={
            "cap_id": cap.id,
            "file_path": self._normalize_path(reference.file_path),
            "approved_by": None,
            "approved_at": None,
            "locked": False,
            "status": CanonicalReferenceStatus.IMPORTED,
        })
        try:
            created = self.repository.create(normalized)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        self._logger.info("Canonical reference created: CAP %s, reference %s", cap.asset_id, created.id)
        return created

    def get(self, reference_id: int) -> CanonicalReference:
        self._require_project()
        try:
            reference = self.repository.get(reference_id)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        if reference is None:
            raise CanonicalReferenceNotFoundError(f"Canonical reference not found: {reference_id}")
        return reference

    def list_for_cap(self, asset_id: str, *, reference_type: CanonicalReferenceType | None = None, status: CanonicalReferenceStatus | None = None) -> tuple[CanonicalReference, ...]:
        cap = self.caps.get(asset_id)
        try:
            return self.repository.list_for_cap(cap.id, reference_type=reference_type, status=status)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc

    def update(self, reference_id: int, changes: CanonicalReferenceUpdate) -> CanonicalReference:
        reference = self.get(reference_id)
        if reference.locked:
            raise CanonicalReferenceLockedError("Approved canonical references are locked. Unlock the reference before editing it.")
        values = changes.model_dump(exclude_unset=True)
        values.pop("approved_by", None)
        values.pop("approved_at", None)
        values.pop("locked", None)
        if "file_path" in values and changes.file_path is not None:
            values["file_path"] = self._normalize_path(changes.file_path)
        if values.get("status") is CanonicalReferenceStatus.APPROVED:
            raise InvalidCanonicalReferenceTransitionError("Use approve() to approve a canonical reference")
        return self._repository_update(reference_id, CanonicalReferenceUpdate.model_validate(values))

    def mark_candidate(self, reference_id: int) -> CanonicalReference:
        reference = self.get(reference_id)
        if reference.locked:
            raise CanonicalReferenceLockedError("Unlock an approved reference before returning it to review")
        if reference.status not in {CanonicalReferenceStatus.IMPORTED, CanonicalReferenceStatus.CANDIDATE}:
            raise InvalidCanonicalReferenceTransitionError(f"Cannot mark a {reference.status.value} reference as candidate")
        return self._repository_update(reference_id, CanonicalReferenceUpdate(status=CanonicalReferenceStatus.CANDIDATE))

    def approve(self, reference_id: int, approved_by: str) -> CanonicalReference:
        reference = self.get(reference_id)
        approver = approved_by.strip()
        if not approver:
            raise ValueError("Approved by is required")
        if reference.status is not CanonicalReferenceStatus.CANDIDATE:
            raise InvalidCanonicalReferenceTransitionError("Only candidate references can be approved")
        if reference.role is CanonicalReferenceRole.PRIMARY:
            self._demote_other_approved_primaries(reference)
        return self._repository_update(reference_id, CanonicalReferenceUpdate(
            status=CanonicalReferenceStatus.APPROVED,
            approved_by=approver,
            approved_at=datetime.now(UTC),
            locked=True,
        ))

    def reject(self, reference_id: int) -> CanonicalReference:
        reference = self.get(reference_id)
        if reference.status is not CanonicalReferenceStatus.APPROVED:
            raise InvalidCanonicalReferenceTransitionError("Only approved references can be rejected")
        return self._repository_update(reference_id, CanonicalReferenceUpdate(
            status=CanonicalReferenceStatus.CANDIDATE,
            approved_by=None,
            approved_at=None,
            locked=False,
        ))

    def archive(self, reference_id: int) -> CanonicalReference:
        reference = self.get(reference_id)
        if reference.status is CanonicalReferenceStatus.ARCHIVED:
            return reference
        return self._repository_update(reference_id, CanonicalReferenceUpdate(
            status=CanonicalReferenceStatus.ARCHIVED,
            approved_by=None,
            approved_at=None,
            locked=True,
        ))

    def unlock(self, reference_id: int) -> CanonicalReference:
        reference = self.get(reference_id)
        if not reference.locked:
            return reference
        return self._repository_update(reference_id, CanonicalReferenceUpdate(
            status=CanonicalReferenceStatus.CANDIDATE,
            approved_by=None,
            approved_at=None,
            locked=False,
        ))

    def set_primary(self, reference_id: int) -> CanonicalReference:
        target = self.get(reference_id)
        if target.locked:
            raise CanonicalReferenceLockedError("Unlock the reference before changing its role")
        try:
            references = self.repository.list_for_cap(target.cap_id)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        for reference in references:
            if reference.id != reference_id and reference.role is CanonicalReferenceRole.PRIMARY:
                if reference.locked:
                    continue
                self._repository_update(reference.id, CanonicalReferenceUpdate(role=CanonicalReferenceRole.SECONDARY))
        return self._repository_update(reference_id, CanonicalReferenceUpdate(role=CanonicalReferenceRole.PRIMARY))

    def delete(self, reference_id: int) -> None:
        reference = self.get(reference_id)
        if reference.locked:
            raise CanonicalReferenceLockedError("Unlock the canonical reference before removing it")
        try:
            deleted = self.repository.delete(reference_id)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        if not deleted:
            raise CanonicalReferenceNotFoundError(f"Canonical reference not found: {reference_id}")
        self._logger.info("Canonical reference deleted: %s", reference_id)

    def _demote_other_approved_primaries(self, target: CanonicalReference) -> None:
        try:
            references = self.repository.list_for_cap(target.cap_id)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        for reference in references:
            if reference.id != target.id and reference.role is CanonicalReferenceRole.PRIMARY and reference.status is CanonicalReferenceStatus.APPROVED:
                self._repository_update(reference.id, CanonicalReferenceUpdate(role=CanonicalReferenceRole.SECONDARY))

    def _repository_update(self, reference_id: int, changes: CanonicalReferenceUpdate) -> CanonicalReference:
        try:
            updated = self.repository.update(reference_id, changes)
        except CanonicalReferenceRepositoryError as exc:
            raise CanonicalReferenceError(str(exc)) from exc
        if updated is None:
            raise CanonicalReferenceNotFoundError(f"Canonical reference not found: {reference_id}")
        self._logger.info("Canonical reference updated: %s", reference_id)
        return updated

    def _require_project(self) -> Path:
        project_directory = self.caps.assets.projects.project_directory
        if not self.caps.assets.projects.is_project_open or project_directory is None:
            raise CanonicalReferenceError("Open a VSCS project before managing canonical references")
        return project_directory

    def _normalize_path(self, path: Path) -> Path:
        root = self._require_project().resolve(strict=False)
        resolved = path.expanduser().resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
        try:
            return resolved.relative_to(root)
        except ValueError as exc:
            raise InvalidCanonicalReferencePathError(f"Canonical reference files must be inside the active project: {resolved}") from exc
