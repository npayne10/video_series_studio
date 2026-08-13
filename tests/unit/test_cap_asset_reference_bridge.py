from pathlib import Path
from types import SimpleNamespace

from vscs.application.caps.asset_reference_bridge import ensure_asset_image_reference
from vscs.domain.caps import (
    CanonicalReference,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
)


class _References:
    def __init__(self, root: Path) -> None:
        self.caps = SimpleNamespace(
            assets=SimpleNamespace(
                projects=SimpleNamespace(project_directory=root),
                get=lambda _asset_id: SimpleNamespace(
                    asset_id="CAP-CHR-002",
                    file_path=Path("assets/characters/CAP-CHR-002.png"),
                ),
            ),
            get=lambda _asset_id: SimpleNamespace(id=2, title="Captain Cheryl Draker"),
        )
        self.values: list[CanonicalReference] = []
        self.create_calls = 0

    def list_for_cap(self, _asset_id: str) -> tuple[CanonicalReference, ...]:
        return tuple(self.values)

    def create(self, _asset_id: str, value: object) -> CanonicalReference:
        self.create_calls += 1
        reference = CanonicalReference(
            id=1,
            cap_id=2,
            reference_type=CanonicalReferenceType.IMAGE,
            role=CanonicalReferenceRole.PRIMARY,
            title="Captain Cheryl Draker Canonical Reference",
            file_path=Path("assets/characters/CAP-CHR-002.png"),
            description="",
            notes="",
            version="1.0",
            status=CanonicalReferenceStatus.IMPORTED,
        )
        self.values = [reference]
        return reference

    def mark_candidate(self, reference_id: int) -> CanonicalReference:
        value = self.values[0].model_copy(update={"status": CanonicalReferenceStatus.CANDIDATE})
        self.values = [value]
        return value

    def set_primary(self, reference_id: int) -> CanonicalReference:
        return self.values[0]

    def approve(self, reference_id: int, approved_by: str) -> CanonicalReference:
        value = self.values[0].model_copy(
            update={"status": CanonicalReferenceStatus.APPROVED, "locked": True}
        )
        self.values = [value]
        return value


def test_asset_image_becomes_approved_primary_reference_without_copying(tmp_path: Path) -> None:
    references = _References(tmp_path)

    result = ensure_asset_image_reference(references, "CAP-CHR-002")  # type: ignore[arg-type]

    assert result is not None
    assert result.status is CanonicalReferenceStatus.APPROVED
    assert result.role is CanonicalReferenceRole.PRIMARY
    assert result.file_path == Path("assets/characters/CAP-CHR-002.png")
    assert references.create_calls == 1


def test_asset_reference_bridge_is_idempotent(tmp_path: Path) -> None:
    references = _References(tmp_path)
    first = ensure_asset_image_reference(references, "CAP-CHR-002")  # type: ignore[arg-type]
    second = ensure_asset_image_reference(references, "CAP-CHR-002")  # type: ignore[arg-type]

    assert first is not None
    assert second is first
    assert references.create_calls == 1
