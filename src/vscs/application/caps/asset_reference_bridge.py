"""Bridge existing Asset image paths into CAP reference records."""

from __future__ import annotations

from pathlib import Path

from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.domain.caps import (
    CanonicalReference,
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
)

_IMAGE_SUFFIXES = frozenset({".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"})


def ensure_asset_image_reference(
    references: CanonicalReferenceService,
    asset_id: str,
) -> CanonicalReference | None:
    asset = references.caps.assets.get(asset_id)
    source = asset.file_path
    if source is None or source.suffix.lower() not in _IMAGE_SUFFIXES:
        return None

    source_key = _path_key(references, source)
    existing = references.list_for_cap(asset.asset_id)
    match = next(
        (item for item in existing if _path_key(references, item.file_path) == source_key),
        None,
    )
    if match is not None:
        return match

    profile = references.caps.get(asset.asset_id)
    created = references.create(
        asset.asset_id,
        CanonicalReferenceCreate(
            cap_id=profile.id,
            reference_type=CanonicalReferenceType.IMAGE,
            role=CanonicalReferenceRole.PRIMARY,
            title=f"{profile.title} Canonical Reference",
            file_path=source,
            description="Reference inherited from the Asset record.",
            notes="Source image reused without copying.",
            version="1.0",
        ),
    )
    candidate = references.mark_candidate(created.id)
    primary = references.set_primary(candidate.id)
    if primary.status is CanonicalReferenceStatus.CANDIDATE:
        return references.approve(primary.id, "VSCS Asset Reference Bridge")
    return primary


def _path_key(references: CanonicalReferenceService, path: Path) -> str:
    root = references.caps.assets.projects.project_directory
    absolute = path if path.is_absolute() or root is None else root / path
    return str(absolute.resolve(strict=False)).replace("/", "\\").casefold()
