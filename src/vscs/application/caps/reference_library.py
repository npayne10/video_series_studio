"""Application service for the CAP production reference library and lifecycle."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.domain.caps import CanonicalReference, CanonicalReferenceStatus
from vscs.domain.caps.production_contract import (
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceOrigin,
    CanonicalReferenceView,
    ProductionReference,
)
from vscs.domain.caps.reference_library import (
    ReferenceLibraryEntry,
    ReferenceLibrarySnapshot,
    ReferenceLifecycleAction,
    ReferenceLifecycleEvent,
)


class ReferenceLibraryError(RuntimeError):
    """Base exception for production reference-library failures."""


class ReferenceLibraryNotFoundError(ReferenceLibraryError):
    """Raised when a reference has no production-library registration."""


class ReferenceLibraryConflictError(ReferenceLibraryError):
    """Raised when a registration violates canonical reference invariants."""


class InvalidReferenceLifecycleTransitionError(ReferenceLibraryError):
    """Raised when a requested production lifecycle transition is invalid."""


class ReferenceLibraryStore:
    """Persist production reference metadata without changing the legacy DB schema."""

    FILE_NAME = "cap_reference_library.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    @property
    def path(self) -> Path:
        return self.project_directory / ".vscs" / self.FILE_NAME

    def load(self) -> ReferenceLibrarySnapshot:
        if not self.path.exists():
            return ReferenceLibrarySnapshot()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return ReferenceLibrarySnapshot.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ReferenceLibraryError(
                f"Unable to read CAP reference library {self.path}: {exc}"
            ) from exc

    def save(self, snapshot: ReferenceLibrarySnapshot) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(snapshot.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            raise ReferenceLibraryError(
                f"Unable to save CAP reference library {self.path}: {exc}"
            ) from exc


class ReferenceLibraryService:
    """Govern MASTER and derived reference metadata over structured DB references."""

    def __init__(self, references: CanonicalReferenceService) -> None:
        self.references = references

    def register_master(
        self,
        asset_id: str,
        reference_record_id: int,
        *,
        reference_id: str | None = None,
        actor: str = "",
        note: str = "",
    ) -> ReferenceLibraryEntry:
        reference = self._require_reference_for_asset(asset_id, reference_record_id)
        snapshot = self._store().load()
        existing = self._entry_for_record(snapshot, reference_record_id)
        if existing is not None:
            if existing.family is CanonicalReferenceFamily.MASTER:
                return existing
            raise ReferenceLibraryConflictError(
                f"Reference record {reference_record_id} is already registered as "
                f"{existing.family.value}"
            )
        if self._active_master(snapshot, asset_id) is not None:
            raise ReferenceLibraryConflictError(
                f"CAP {asset_id.upper()} already has an active MASTER reference"
            )
        entry = ReferenceLibraryEntry(
            reference_record_id=reference_record_id,
            asset_id=asset_id.upper(),
            reference_id=reference_id or self._reference_id(asset_id, reference_record_id),
            family=CanonicalReferenceFamily.MASTER,
            view=CanonicalReferenceView.MASTER,
            origin=CanonicalReferenceOrigin.CHATGPT_MASTER,
            lifecycle=CanonicalReferenceLifecycle.CANDIDATE,
            history=(
                self._event(
                    ReferenceLifecycleAction.REGISTER,
                    actor=actor,
                    note=note or "ChatGPT-authored MASTER registered",
                    to_lifecycle=CanonicalReferenceLifecycle.CANDIDATE,
                ),
            ),
        )
        self._save_entry(snapshot, entry)
        self._ensure_legacy_candidate(reference_record_id, reference.status)
        return entry

    def register_derived(
        self,
        asset_id: str,
        reference_record_id: int,
        *,
        family: CanonicalReferenceFamily,
        view: CanonicalReferenceView,
        generator: str,
        reference_id: str | None = None,
        actor: str = "",
        note: str = "",
    ) -> ReferenceLibraryEntry:
        reference = self._require_reference_for_asset(asset_id, reference_record_id)
        generator_name = generator.strip()
        if not generator_name:
            raise ValueError("Derived reference generator is required")
        if family is CanonicalReferenceFamily.MASTER or view is CanonicalReferenceView.MASTER:
            raise ReferenceLibraryConflictError(
                "Derived references cannot use the MASTER family or MASTER view"
            )
        snapshot = self._store().load()
        existing = self._entry_for_record(snapshot, reference_record_id)
        if existing is not None:
            return existing
        master = self._active_master(snapshot, asset_id)
        if master is None:
            raise ReferenceLibraryConflictError(
                f"CAP {asset_id.upper()} requires a registered MASTER before derived references"
            )
        master_reference = self.references.get(master.reference_record_id)
        entry = ReferenceLibraryEntry(
            reference_record_id=reference_record_id,
            asset_id=asset_id.upper(),
            reference_id=reference_id or self._reference_id(asset_id, reference_record_id),
            family=family,
            view=view,
            origin=CanonicalReferenceOrigin.VSCS_DERIVED,
            lifecycle=CanonicalReferenceLifecycle.CANDIDATE,
            parent_reference_id=master.reference_id,
            generator=generator_name,
            source_master_version=master_reference.version,
            history=(
                self._event(
                    ReferenceLifecycleAction.REGISTER,
                    actor=actor,
                    note=note or f"Derived {view.value} reference registered",
                    to_lifecycle=CanonicalReferenceLifecycle.CANDIDATE,
                ),
            ),
        )
        self._save_entry(snapshot, entry)
        self._ensure_legacy_candidate(reference_record_id, reference.status)
        return entry

    def get(self, reference_record_id: int) -> ReferenceLibraryEntry:
        entry = self._entry_for_record(self._store().load(), reference_record_id)
        if entry is None:
            raise ReferenceLibraryNotFoundError(
                f"Reference record {reference_record_id} is not registered in the production library"
            )
        return entry

    def list_for_cap(
        self,
        asset_id: str,
        *,
        include_archived: bool = False,
    ) -> tuple[ReferenceLibraryEntry, ...]:
        normalized = asset_id.upper()
        entries = tuple(
            entry
            for entry in self._store().load().entries
            if entry.asset_id == normalized
            and (include_archived or entry.lifecycle is not CanonicalReferenceLifecycle.ARCHIVED)
        )
        return tuple(
            sorted(
                entries,
                key=lambda item: (item.family.value, item.view.value, item.reference_id),
            )
        )

    def mark_candidate(
        self,
        reference_record_id: int,
        *,
        actor: str = "",
        note: str = "",
    ) -> ReferenceLibraryEntry:
        entry = self.get(reference_record_id)
        if entry.lifecycle is CanonicalReferenceLifecycle.CANDIDATE:
            return entry
        if entry.lifecycle is not CanonicalReferenceLifecycle.REJECTED:
            raise InvalidReferenceLifecycleTransitionError(
                f"Cannot mark a {entry.lifecycle.value} reference as candidate"
            )
        self._ensure_legacy_candidate(
            reference_record_id,
            self.references.get(reference_record_id).status,
        )
        return self._transition(
            entry,
            CanonicalReferenceLifecycle.CANDIDATE,
            ReferenceLifecycleAction.RETURN_TO_CANDIDATE,
            actor,
            note,
        )

    def approve(
        self,
        reference_record_id: int,
        approved_by: str,
        *,
        note: str = "",
    ) -> ReferenceLibraryEntry:
        entry = self.get(reference_record_id)
        if entry.lifecycle is not CanonicalReferenceLifecycle.CANDIDATE:
            raise InvalidReferenceLifecycleTransitionError("Only candidate references can be approved")
        approver = approved_by.strip()
        if not approver:
            raise ValueError("Approved by is required")
        reference = self.references.get(reference_record_id)
        if reference.status is CanonicalReferenceStatus.IMPORTED:
            self.references.mark_candidate(reference_record_id)
        reference = self.references.get(reference_record_id)
        if reference.status is CanonicalReferenceStatus.CANDIDATE:
            self.references.approve(reference_record_id, approver)
        now = datetime.now(UTC)
        return self._transition(
            entry,
            CanonicalReferenceLifecycle.APPROVED,
            ReferenceLifecycleAction.APPROVE,
            approver,
            note,
            approval=(approver, now),
        )

    def lock(
        self,
        reference_record_id: int,
        *,
        actor: str = "",
        note: str = "",
    ) -> ReferenceLibraryEntry:
        entry = self.get(reference_record_id)
        if entry.lifecycle is CanonicalReferenceLifecycle.LOCKED:
            return entry
        if entry.lifecycle is not CanonicalReferenceLifecycle.APPROVED:
            raise InvalidReferenceLifecycleTransitionError("Only approved references can be locked")
        return self._transition(
            entry,
            CanonicalReferenceLifecycle.LOCKED,
            ReferenceLifecycleAction.LOCK,
            actor,
            note,
        )

    def reject(
        self,
        reference_record_id: int,
        *,
        actor: str = "",
        note: str = "",
    ) -> ReferenceLibraryEntry:
        entry = self.get(reference_record_id)
        if entry.lifecycle not in {
            CanonicalReferenceLifecycle.CANDIDATE,
            CanonicalReferenceLifecycle.APPROVED,
        }:
            raise InvalidReferenceLifecycleTransitionError(
                f"Cannot reject a {entry.lifecycle.value} reference"
            )
        reference = self.references.get(reference_record_id)
        if reference.status is CanonicalReferenceStatus.APPROVED:
            self.references.reject(reference_record_id)
        return self._transition(
            entry,
            CanonicalReferenceLifecycle.REJECTED,
            ReferenceLifecycleAction.REJECT,
            actor,
            note,
            clear_approval=True,
        )

    def return_to_candidate(
        self,
        reference_record_id: int,
        *,
        actor: str = "",
        note: str = "",
    ) -> ReferenceLibraryEntry:
        entry = self.get(reference_record_id)
        if entry.lifecycle is CanonicalReferenceLifecycle.LOCKED:
            raise InvalidReferenceLifecycleTransitionError(
                "Locked references require archival/version replacement; "
                "they cannot be silently reopened"
            )
        if entry.lifecycle is CanonicalReferenceLifecycle.REJECTED:
            return self.mark_candidate(reference_record_id, actor=actor, note=note)
        if entry.lifecycle is not CanonicalReferenceLifecycle.APPROVED:
            raise InvalidReferenceLifecycleTransitionError(
                f"Cannot return a {entry.lifecycle.value} reference to candidate"
            )
        reference = self.references.get(reference_record_id)
        if reference.locked:
            self.references.unlock(reference_record_id)
        return self._transition(
            entry,
            CanonicalReferenceLifecycle.CANDIDATE,
            ReferenceLifecycleAction.RETURN_TO_CANDIDATE,
            actor,
            note,
            clear_approval=True,
        )

    def archive(
        self,
        reference_record_id: int,
        *,
        actor: str = "",
        note: str = "",
    ) -> ReferenceLibraryEntry:
        entry = self.get(reference_record_id)
        if entry.lifecycle is CanonicalReferenceLifecycle.ARCHIVED:
            return entry
        if entry.family is CanonicalReferenceFamily.MASTER:
            active_dependants = tuple(
                candidate
                for candidate in self.list_for_cap(entry.asset_id)
                if candidate.parent_reference_id == entry.reference_id
                and candidate.lifecycle is not CanonicalReferenceLifecycle.ARCHIVED
            )
            if active_dependants:
                raise ReferenceLibraryConflictError(
                    "Archive dependent derived references before archiving the active MASTER"
                )
        self.references.archive(reference_record_id)
        return self._transition(
            entry,
            CanonicalReferenceLifecycle.ARCHIVED,
            ReferenceLifecycleAction.ARCHIVE,
            actor,
            note,
        )

    def production_reference(self, reference_record_id: int) -> ProductionReference:
        entry = self.get(reference_record_id)
        reference = self.references.get(reference_record_id)
        return ProductionReference(
            reference_id=entry.reference_id,
            family=entry.family,
            view=entry.view,
            origin=entry.origin,
            lifecycle=entry.lifecycle,
            version=reference.version,
            parent_reference_id=entry.parent_reference_id,
            file_path=str(reference.file_path),
            generator=entry.generator,
            approved_by=entry.approved_by,
        )

    def _require_reference_for_asset(
        self,
        asset_id: str,
        reference_record_id: int,
    ) -> CanonicalReference:
        cap = self.references.caps.get(asset_id)
        reference = self.references.get(reference_record_id)
        if reference.cap_id != cap.id:
            raise ReferenceLibraryConflictError(
                f"Reference record {reference_record_id} does not belong to CAP {asset_id.upper()}"
            )
        return reference

    def _store(self) -> ReferenceLibraryStore:
        project_directory = self.references.caps.assets.projects.project_directory
        if not self.references.caps.assets.projects.is_project_open or project_directory is None:
            raise ReferenceLibraryError(
                "Open a VSCS project before managing the CAP reference library"
            )
        return ReferenceLibraryStore(project_directory)

    @staticmethod
    def _entry_for_record(
        snapshot: ReferenceLibrarySnapshot,
        reference_record_id: int,
    ) -> ReferenceLibraryEntry | None:
        return next(
            (
                entry
                for entry in snapshot.entries
                if entry.reference_record_id == reference_record_id
            ),
            None,
        )

    @staticmethod
    def _active_master(
        snapshot: ReferenceLibrarySnapshot,
        asset_id: str,
    ) -> ReferenceLibraryEntry | None:
        normalized = asset_id.upper()
        return next(
            (
                entry
                for entry in snapshot.entries
                if entry.asset_id == normalized
                and entry.family is CanonicalReferenceFamily.MASTER
                and entry.lifecycle is not CanonicalReferenceLifecycle.ARCHIVED
            ),
            None,
        )

    def _save_entry(
        self,
        snapshot: ReferenceLibrarySnapshot,
        entry: ReferenceLibraryEntry,
    ) -> None:
        entries = tuple(
            *(
            existing
            for existing in snapshot.entries
            if existing.reference_record_id != entry.reference_record_id
            ),
            entry,
        )
        self._store().save(ReferenceLibrarySnapshot(entries=entries))

    def _transition(
        self,
        entry: ReferenceLibraryEntry,
        lifecycle: CanonicalReferenceLifecycle,
        action: ReferenceLifecycleAction,
        actor: str,
        note: str,
        *,
        approval: tuple[str, datetime] | None = None,
        clear_approval: bool = False,
    ) -> ReferenceLibraryEntry:
        now = datetime.now(UTC)
        updates: dict[str, object] = {
            "lifecycle": lifecycle,
            "updated_at": now,
            "history": (
                *entry.history,
                self._event(
                    action,
                    actor=actor,
                    note=note,
                    from_lifecycle=entry.lifecycle,
                    to_lifecycle=lifecycle,
                    at=now,
                ),
            ),
        }
        if approval is not None:
            updates["approved_by"], updates["approved_at"] = approval
        elif clear_approval:
            updates["approved_by"] = None
            updates["approved_at"] = None
        updated = entry.model_copy(update=updates)
        snapshot = self._store().load()
        self._save_entry(snapshot, updated)
        return updated

    def _ensure_legacy_candidate(
        self,
        reference_record_id: int,
        status: CanonicalReferenceStatus,
    ) -> None:
        if status is CanonicalReferenceStatus.IMPORTED:
            self.references.mark_candidate(reference_record_id)
        elif status is CanonicalReferenceStatus.ARCHIVED:
            raise InvalidReferenceLifecycleTransitionError(
                "Archived legacy references cannot be registered as active production references"
            )

    @staticmethod
    def _reference_id(asset_id: str, reference_record_id: int) -> str:
        return f"{asset_id.upper()}-REF-{reference_record_id:04d}"

    @staticmethod
    def _event(
        action: ReferenceLifecycleAction,
        *,
        actor: str = "",
        note: str = "",
        from_lifecycle: CanonicalReferenceLifecycle | None = None,
        to_lifecycle: CanonicalReferenceLifecycle | None = None,
        at: datetime | None = None,
    ) -> ReferenceLifecycleEvent:
        return ReferenceLifecycleEvent(
            action=action,
            at=at or datetime.now(UTC),
            actor=actor,
            note=note,
            from_lifecycle=from_lifecycle,
            to_lifecycle=to_lifecycle,
        )
