"""Managed file storage for Canonical Asset Profile references."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from vscs.domain.caps import CanonicalReferenceType


class CanonicalReferenceFileError(RuntimeError):
    """Raised when a canonical reference file cannot be managed safely."""


class DuplicateFileResolution(StrEnum):
    """Supported responses when a managed destination already exists."""

    REPLACE = "replace"
    KEEP_BOTH = "keep_both"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class ManagedReferenceFile:
    """Result of importing one file into project-owned canonical storage."""

    relative_path: Path
    reference_type: CanonicalReferenceType
    sha256: str
    size_bytes: int
    modified_at: str


class CanonicalReferenceFileManager:
    """Own canonical reference directories, imports, integrity data, and caches."""

    TYPE_DIRECTORIES = {
        CanonicalReferenceType.IMAGE: "Images",
        CanonicalReferenceType.DOCUMENT: "Documents",
        CanonicalReferenceType.AUDIO: "Audio",
        CanonicalReferenceType.VIDEO: "Video",
        CanonicalReferenceType.MATERIAL: "Materials",
    }
    EXTENSION_TYPES = {
        ".png": CanonicalReferenceType.IMAGE,
        ".jpg": CanonicalReferenceType.IMAGE,
        ".jpeg": CanonicalReferenceType.IMAGE,
        ".webp": CanonicalReferenceType.IMAGE,
        ".bmp": CanonicalReferenceType.IMAGE,
        ".gif": CanonicalReferenceType.IMAGE,
        ".tif": CanonicalReferenceType.IMAGE,
        ".tiff": CanonicalReferenceType.IMAGE,
        ".pdf": CanonicalReferenceType.DOCUMENT,
        ".doc": CanonicalReferenceType.DOCUMENT,
        ".docx": CanonicalReferenceType.DOCUMENT,
        ".txt": CanonicalReferenceType.DOCUMENT,
        ".md": CanonicalReferenceType.DOCUMENT,
        ".rtf": CanonicalReferenceType.DOCUMENT,
        ".xlsx": CanonicalReferenceType.DOCUMENT,
        ".wav": CanonicalReferenceType.AUDIO,
        ".mp3": CanonicalReferenceType.AUDIO,
        ".flac": CanonicalReferenceType.AUDIO,
        ".ogg": CanonicalReferenceType.AUDIO,
        ".m4a": CanonicalReferenceType.AUDIO,
        ".mp4": CanonicalReferenceType.VIDEO,
        ".mov": CanonicalReferenceType.VIDEO,
        ".mkv": CanonicalReferenceType.VIDEO,
        ".avi": CanonicalReferenceType.VIDEO,
        ".webm": CanonicalReferenceType.VIDEO,
        ".exr": CanonicalReferenceType.MATERIAL,
        ".hdr": CanonicalReferenceType.MATERIAL,
        ".sbsar": CanonicalReferenceType.MATERIAL,
        ".mtl": CanonicalReferenceType.MATERIAL,
    }

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory.expanduser().resolve(strict=False)

    @property
    def canonical_assets_directory(self) -> Path:
        return self.project_directory / "Canonical Assets"

    @property
    def thumbnail_cache_directory(self) -> Path:
        return self.project_directory / "Cache" / "Thumbnails"

    def ensure_asset_structure(self, asset_id: str) -> Path:
        """Create and return the complete managed directory tree for one CAP."""
        root = self.canonical_assets_directory / self._safe_asset_id(asset_id)
        for directory in self.TYPE_DIRECTORIES.values():
            (root / directory).mkdir(parents=True, exist_ok=True)
        (root / ".metadata").mkdir(parents=True, exist_ok=True)
        self.thumbnail_cache_directory.mkdir(parents=True, exist_ok=True)
        return root

    def detect_type(self, source: Path) -> CanonicalReferenceType:
        """Infer a canonical reference category from extension and MIME type."""
        suffix = source.suffix.lower()
        known = self.EXTENSION_TYPES.get(suffix)
        if known is not None:
            return known
        mime_type, _ = mimetypes.guess_type(source.name)
        if mime_type:
            family = mime_type.split("/", 1)[0]
            if family == "image":
                return CanonicalReferenceType.IMAGE
            if family == "audio":
                return CanonicalReferenceType.AUDIO
            if family == "video":
                return CanonicalReferenceType.VIDEO
            if family == "text" or mime_type == "application/pdf":
                return CanonicalReferenceType.DOCUMENT
        return CanonicalReferenceType.DOCUMENT

    def destination_for(
        self,
        asset_id: str,
        source: Path,
        reference_type: CanonicalReferenceType,
    ) -> Path:
        root = self.ensure_asset_structure(asset_id)
        return root / self.TYPE_DIRECTORIES[reference_type] / source.name

    def import_file(
        self,
        asset_id: str,
        source: Path,
        *,
        reference_type: CanonicalReferenceType | None = None,
        duplicate_resolution: DuplicateFileResolution = DuplicateFileResolution.KEEP_BOTH,
    ) -> ManagedReferenceFile:
        """Copy a source file into canonical storage and record integrity metadata."""
        source = source.expanduser().resolve(strict=False)
        if not source.is_file():
            raise CanonicalReferenceFileError(f"Reference source file does not exist: {source}")
        reference_type = reference_type or self.detect_type(source)
        destination = self.destination_for(asset_id, source, reference_type)
        if destination.exists():
            if source == destination:
                return self.inspect(destination, reference_type)
            if duplicate_resolution is DuplicateFileResolution.CANCEL:
                raise CanonicalReferenceFileError("Canonical reference import was cancelled")
            if duplicate_resolution is DuplicateFileResolution.KEEP_BOTH:
                destination = self._next_available_path(destination)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except OSError as exc:
            raise CanonicalReferenceFileError(
                f"Unable to copy canonical reference to {destination}: {exc}"
            ) from exc
        managed = self.inspect(destination, reference_type)
        self._write_integrity_metadata(asset_id, managed)
        return managed

    def inspect(
        self,
        path: Path,
        reference_type: CanonicalReferenceType | None = None,
    ) -> ManagedReferenceFile:
        """Calculate portable path and integrity metadata for a managed file."""
        absolute = path if path.is_absolute() else self.project_directory / path
        absolute = absolute.resolve(strict=False)
        if not absolute.is_file():
            raise CanonicalReferenceFileError(f"Canonical reference file is missing: {absolute}")
        try:
            relative = absolute.relative_to(self.project_directory)
        except ValueError as exc:
            raise CanonicalReferenceFileError(
                f"Canonical references must remain inside the project: {absolute}"
            ) from exc
        stat = absolute.stat()
        return ManagedReferenceFile(
            relative_path=relative,
            reference_type=reference_type or self.detect_type(absolute),
            sha256=self._sha256(absolute),
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        )

    def _write_integrity_metadata(self, asset_id: str, managed: ManagedReferenceFile) -> None:
        metadata_root = self.ensure_asset_structure(asset_id) / ".metadata"
        key = hashlib.sha256(str(managed.relative_path).encode("utf-8")).hexdigest()
        payload = asdict(managed)
        payload["relative_path"] = str(managed.relative_path)
        payload["reference_type"] = managed.reference_type.value
        payload["recorded_at"] = datetime.now(UTC).isoformat()
        try:
            (metadata_root / f"{key}.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            raise CanonicalReferenceFileError(
                f"Unable to write canonical reference integrity metadata: {exc}"
            ) from exc

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _next_available_path(path: Path) -> Path:
        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _safe_asset_id(asset_id: str) -> str:
        normalized = asset_id.strip().upper()
        if not normalized or any(part in normalized for part in ("/", "\\", "..")):
            raise CanonicalReferenceFileError(f"Invalid CAP asset ID: {asset_id}")
        return normalized
