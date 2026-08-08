"""Integration coverage for the Phase 18.2.11.2.3 reference-library pipeline."""

from pathlib import Path
from types import SimpleNamespace

from vscs.application.caps import ReferenceLibraryService, ReferenceLibraryStore
from vscs.domain.caps import (
    CanonicalReference,
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CanonicalReferenceView,
)


class _ReferenceService:
    def __init__(self, project_directory: Path) -> None:
        projects = SimpleNamespace(is_project_open=True, project_directory=project_directory)
        assets = SimpleNamespace(projects=projects)
        self.caps = SimpleNamespace(assets=assets, get=lambda asset_id: SimpleNamespace(id=1))
        self._values = {
            11: self._reference(11, "master.png"),
            12: self._reference(12, "port.png"),
        }

    @staticmethod
    def _reference(reference_id: int, filename: str) -> CanonicalReference:
        return CanonicalReference(
            id=reference_id,
            cap_id=1,
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
        return self._values[reference_id]

    def mark_candidate(self, reference_id: int) -> CanonicalReference:
        return self._replace(reference_id, status=CanonicalReferenceStatus.CANDIDATE)

    def approve(self, reference_id: int, approved_by: str) -> CanonicalReference:
        return self._replace(
            reference_id,
            status=CanonicalReferenceStatus.APPROVED,
            approved_by=approved_by,
            locked=True,
        )

    def archive(self, reference_id: int) -> CanonicalReference:
        return self._replace(
            reference_id,
            status=CanonicalReferenceStatus.ARCHIVED,
            locked=True,
        )

    def reject(self, reference_id: int) -> CanonicalReference:
        return self._replace(
            reference_id,
            status=CanonicalReferenceStatus.CANDIDATE,
            approved_by=None,
            locked=False,
        )

    def unlock(self, reference_id: int) -> CanonicalReference:
        return self._replace(
            reference_id,
            status=CanonicalReferenceStatus.CANDIDATE,
            approved_by=None,
            locked=False,
        )

    def _replace(self, reference_id: int, **changes: object) -> CanonicalReference:
        value = self._values[reference_id].model_copy(update=changes)
        self._values[reference_id] = value
        return value


def test_reference_library_survives_service_restart_and_preserves_lineage(tmp_path: Path) -> None:
    references = _ReferenceService(tmp_path)
    service = ReferenceLibraryService(references)  # type: ignore[arg-type]

    master = service.register_master("CAP-SHP-004", 11, actor="Neill")
    derived = service.register_derived(
        "CAP-SHP-004",
        12,
        family=CanonicalReferenceFamily.PRODUCTION_VIEW,
        view=CanonicalReferenceView.PORT,
        generator="test-generator",
        actor="Neill",
    )
    service.approve(11, "Neill")
    service.lock(11)
    service.approve(12, "Neill")
    service.lock(12)

    snapshot = ReferenceLibraryStore(tmp_path).load()
    assert len(snapshot.entries) == 2

    restarted = ReferenceLibraryService(references)  # type: ignore[arg-type]
    restored_master = restarted.get(11)
    restored_derived = restarted.get(12)

    assert restored_master.lifecycle is CanonicalReferenceLifecycle.LOCKED
    assert restored_derived.lifecycle is CanonicalReferenceLifecycle.LOCKED
    assert restored_derived.parent_reference_id == master.reference_id
    assert restored_derived.reference_id == derived.reference_id
    assert restored_derived.source_master_version == "1.0"
    assert (tmp_path / ".vscs" / "cap_reference_library.json").is_file()
