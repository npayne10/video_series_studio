"""Local project file-store adapter for Generated Media ingestion."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path, PurePosixPath

from vscs.application.generated_media.ingestion import GeneratedMediaIngestionError
from vscs.domain.generated_media import GeneratedMediaFile


class LocalGeneratedMediaFileStore:
    """Copy provider outputs into a VSCS-managed project media location.

    ``managed_relative_root`` is optional for backward compatibility. When supplied,
    every ingestion destination is rooted beneath that project-relative directory.
    This lets the desktop application honour a project Media Output setting without
    changing the provider-neutral Generated Media ingestion contract.
    """

    def __init__(
        self,
        source_root: Path,
        project_root: Path,
        *,
        managed_relative_root: str | None = None,
    ) -> None:
        self.source_root = Path(source_root).resolve()
        self.project_root = Path(project_root).resolve()
        self.managed_relative_root = self._normalize_managed_root(managed_relative_root)

    def ingest(
        self, source_relative_path: str, destination_relative_path: str
    ) -> GeneratedMediaFile:
        source = self._resolve_relative(self.source_root, source_relative_path, "source")
        destination = self._resolve_relative(
            self.project_root,
            self._managed_destination(destination_relative_path),
            "destination",
        )
        if not source.exists() or not source.is_file():
            raise GeneratedMediaIngestionError(f"provider output file does not exist: {source}")

        source_checksum, source_size = _digest(source)
        if destination.exists():
            if not destination.is_file():
                raise GeneratedMediaIngestionError(
                    f"Generated Media destination is not a file: {destination}"
                )
            destination_checksum, destination_size = _digest(destination)
            if destination_checksum != source_checksum or destination_size != source_size:
                raise GeneratedMediaIngestionError(
                    "Generated Media destination already exists with different content"
                )
            return GeneratedMediaFile(
                relative_path=self._project_relative(destination),
                checksum_sha256=destination_checksum,
                size_bytes=destination_size,
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.ingesting")
        try:
            shutil.copyfile(source, temporary)
            copied_checksum, copied_size = _digest(temporary)
            if copied_checksum != source_checksum or copied_size != source_size:
                raise GeneratedMediaIngestionError(
                    "Generated Media copy verification failed before atomic promotion"
                )
            os.replace(temporary, destination)
        except (OSError, GeneratedMediaIngestionError) as exc:
            temporary.unlink(missing_ok=True)
            if isinstance(exc, GeneratedMediaIngestionError):
                raise
            raise GeneratedMediaIngestionError(
                f"Unable to ingest provider output {source}: {exc}"
            ) from exc

        return GeneratedMediaFile(
            relative_path=self._project_relative(destination),
            checksum_sha256=source_checksum,
            size_bytes=source_size,
        )

    def _managed_destination(self, destination_relative_path: str) -> str:
        normalized = destination_relative_path.strip().replace("\\", "/")
        if not self.managed_relative_root:
            return normalized
        return f"{self.managed_relative_root}/{normalized}"

    @staticmethod
    def _normalize_managed_root(raw_root: str | None) -> str:
        normalized = (raw_root or "").strip().replace("\\", "/").strip("/")
        if not normalized:
            return ""
        pure = PurePosixPath(normalized)
        if pure.is_absolute() or ".." in pure.parts or (pure.parts and ":" in pure.parts[0]):
            raise GeneratedMediaIngestionError(
                "managed media root must remain relative to the configured project root"
            )
        if normalized in {".", ".."}:
            raise GeneratedMediaIngestionError(
                "managed media root must name a project subdirectory"
            )
        return pure.as_posix()

    @staticmethod
    def _resolve_relative(root: Path, raw_path: str, field_name: str) -> Path:
        normalized = raw_path.strip().replace("\\", "/")
        pure = PurePosixPath(normalized)
        if (
            not normalized
            or pure.is_absolute()
            or ".." in pure.parts
            or (pure.parts and ":" in pure.parts[0])
        ):
            raise GeneratedMediaIngestionError(
                f"{field_name} path must remain relative to its configured root"
            )
        candidate = root.joinpath(*pure.parts).resolve()
        if not candidate.is_relative_to(root):
            raise GeneratedMediaIngestionError(f"{field_name} path escapes its configured root")
        return candidate

    def _project_relative(self, path: Path) -> str:
        try:
            return path.relative_to(self.project_root).as_posix()
        except ValueError as exc:
            raise GeneratedMediaIngestionError(
                "Generated Media file is outside the configured project root"
            ) from exc


def _digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise GeneratedMediaIngestionError(f"Unable to read media file {path}: {exc}") from exc
    return digest.hexdigest(), size
