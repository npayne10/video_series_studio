"""Unit tests for the Phase 18.2.11.2.3 reference-library service."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.application.caps import (
    InvalidReferenceLifecycleTransitionError,
    ReferenceLibraryConflictError,
    ReferenceLibraryService,
)
from vscs.domain.caps import (
    CanonicalReference,
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceOrigin,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CanonicalReferenceView,
)


class _References:
    def __init__(self, project_directory: Path) -> None:
        projects = SimpleNamespace(
            is_project_open=True,
            project_directory=project_directory,
        )
        assets = SimpleNamespace(projects=projects)
        self.caps = SimpleNamespace(assets=assets, get=lambda asset_id: SimpleNamespace(id=9))
        self.values = {
            1: self._reference(1, "master.png"),
            2: self._reference(2, "top.png"),
            3: self._reference(3, "front.png"),
        }

    @staticmethod
    def _reference(reference_id: int, filename: str) -> CanonicalReference:
        return CanonicalReference(
            id=reference_id,
            cap_id=9,
            reference_type=CanonicalReferenceType.IMAGE,
            role=CanonicalReferenceRole.SUPPLEMENTARY,
            title=filename,
            file_path=Path("Canonical Assets") / filename,
            description="",
            notes="",
            version="1.0",
            status=CanonicalReferenceStatus.IMPORTED,
            locked=False,
        )

    def get(self, reference_id: int) -> CanonicalReference:
        return self.values[reference_id]

    def mark_candidate(self, reference_id: int) -> CanonicalReference:
        return self._update(
            reference_id,
            status=CanonicalReferenceStatus.CANDIDATE,
            locked=False,
        )

    def approve(self, reference_id: int, approved_by: str) -> CanonicalReference:
        return self._update(
            reference_id,
            status=CanonicalReferenceStatus.APPROVED,
            approved_by=approved_by,
            locked=True,
        )

    def reject(self, reference_id: int) -> CanonicalReference:
        return self._update(
            reference_id,
            status=CanonicalReferenceStatus.CANDIDATE,
            approved_by=None,
            locked=False,
        )

    def archive(self, reference_id: int) -> CanonicalReference:
        return self._update(
            reference_id,
            status=CanonicalReferenceStatus.ARCHIVED,
            locked=True,
        )

    def unlock(self, reference_id: int) -> CanonicalReference:
        return self._update(
            reference_id,
            status=CanonicalReferenceStatus.CANDIDATE,
            approved_by=None,
            locked=False,
        )

    def _update(self, reference_id: int, **changes: object) -> CanonicalReference:
        value = self.values[reference_id].model_copy(update=changes)
        self.values[reference_id] = value
        return value


def test_registers_one_master_and_traceable_derived_reference(tmp_path: Path) -> None:
    references = _References(tmp_path)
    service = ReferenceLibraryService(references)  # type: ignore[arg-type]

    master = service.register_master("CAP-SHP-004", 1, actor="Neill")
    derived = service.register_derived(
        "CAP-SHP-004",
        2,
        family=CanonicalReferenceFamily.PRODUCTION_VIEW,
        view=CanonicalReferenceView.TOP,
        generator="reference-generator-test",
        actor="Neill",
    )

    assert master.family is CanonicalReferenceFamily.MASTER
    assert master.origin is CanonicalReferenceOrigin.CHATGPT_MASTER
    assert derived.origin is CanonicalReferenceOrigin.VSCS_DERIVED
    assert derived.parent_reference_id == master.reference_id
    assert references.get(1).status is CanonicalReferenceStatus.CANDIDATE
    assert references.get(2).status is CanonicalReferenceStatus.CANDIDATE

    reloaded = ReferenceLibraryService(references)  # type: ignore[arg-type]
    assert reloaded.get(1).reference_id == master.reference_id
    assert reloaded.get(2).parent_reference_id == master.reference_id


def test_rejects_second_active_master(tmp_path: Path) -> None:
    service = ReferenceLibraryService(_References(tmp_path))  # type: ignore[arg-type]
    service.register_master("CAP-SHP-004", 1)

    with pytest.raises(ReferenceLibraryConflictError, match="already has an active MASTER"):
        service.register_master("CAP-SHP-004", 2)


def test_candidate_approved_locked_lifecycle_is_audited(tmp_path: Path) -> None:
    references = _References(tmp_path)
    service = ReferenceLibraryService(references)  # type: ignore[arg-type]
    service.register_master("CAP-SHP-004", 1)

    approved = service.approve(1, "Neill")
    locked = service.lock(1, actor="Neill")

    assert approved.lifecycle is CanonicalReferenceLifecycle.APPROVED
    assert approved.approved_by == "Neill"
    assert locked.lifecycle is CanonicalReferenceLifecycle.LOCKED
    assert references.get(1).status is CanonicalReferenceStatus.APPROVED
    assert references.get(1).locked is True
    assert tuple(event.action.value for event in locked.history) == (
        "register",
        "approve",
        "lock",
    )

    with pytest.raises(
        InvalidReferenceLifecycleTransitionError,
        match="cannot be silently reopened",
    ):
        service.return_to_candidate(1)


def test_candidate_can_be_rejected_and_returned_for_review(tmp_path: Path) -> None:
    service = ReferenceLibraryService(_References(tmp_path))  # type: ignore[arg-type]
    service.register_master("CAP-SHP-004", 1)

    rejected = service.reject(1, actor="Reviewer", note="Wrong markings")
    candidate = service.return_to_candidate(1, actor="Reviewer")

    assert rejected.lifecycle is CanonicalReferenceLifecycle.REJECTED
    assert candidate.lifecycle is CanonicalReferenceLifecycle.CANDIDATE
    assert candidate.history[-2].action.value == "reject"
    assert candidate.history[-1].action.value == "return_to_candidate"


def test_master_cannot_archive_before_active_derived_references(tmp_path: Path) -> None:
    service = ReferenceLibraryService(_References(tmp_path))  # type: ignore[arg-type]
    service.register_master("CAP-SHP-004", 1)
    service.register_derived(
        "CAP-SHP-004",
        2,
        family=CanonicalReferenceFamily.PRODUCTION_VIEW,
        view=CanonicalReferenceView.TOP,
        generator="generator",
    )

    with pytest.raises(
        ReferenceLibraryConflictError,
        match="Archive dependent derived references",
    ):
        service.archive(1)

    service.archive(2)
    archived_master = service.archive(1)

    assert archived_master.lifecycle is CanonicalReferenceLifecycle.ARCHIVED


def test_production_reference_projection_preserves_library_semantics(tmp_path: Path) -> None:
    service = ReferenceLibraryService(_References(tmp_path))  # type: ignore[arg-type]
    master = service.register_master("CAP-SHP-004", 1)
    service.approve(1, "Neill")
    service.lock(1)

    production_reference = service.production_reference(1)

    assert production_reference.reference_id == master.reference_id
    assert production_reference.family is CanonicalReferenceFamily.MASTER
    assert production_reference.view is CanonicalReferenceView.MASTER
    assert production_reference.origin is CanonicalReferenceOrigin.CHATGPT_MASTER
    assert production_reference.lifecycle is CanonicalReferenceLifecycle.LOCKED
