"""Governed external evidence ingestion for provider capability validation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from vscs.application.generated_media import GeneratedMediaRepository
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
)


@dataclass(frozen=True, slots=True)
class ValidationEvidenceIngestionResult:
    media: GeneratedMedia
    managed_path: Path


class ValidationEvidenceIngestionService:
    """Copy externally rendered validation evidence into governed VSCS Generated Media."""

    _SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".png", ".jpg", ".jpeg"}

    def __init__(
        self,
        *,
        project_directory: Path,
        media_repository: GeneratedMediaRepository,
    ) -> None:
        self.project_directory = Path(project_directory).resolve(strict=False)
        self.media_repository = media_repository

    def ingest(
        self,
        *,
        source_file: Path,
        provider_id: str,
        session_id: str,
        pack_id: str,
        scenario_id: str,
        criterion_id: str,
        actor: str,
    ) -> ValidationEvidenceIngestionResult:
        source = Path(source_file).expanduser().resolve(strict=False)
        for field_name, value in (
            ("provider_id", provider_id),
            ("session_id", session_id),
            ("pack_id", pack_id),
            ("scenario_id", scenario_id),
            ("criterion_id", criterion_id),
            ("actor", actor),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")
        if not source.is_file():
            raise ValueError(f"validation evidence file does not exist: {source}")
        suffix = source.suffix.casefold()
        if suffix not in self._SUPPORTED_EXTENSIONS:
            raise ValueError(f"unsupported validation evidence type: {suffix or '<none>'}")

        media_id = f"GM-VAL-{uuid4().hex.upper()}"
        destination_dir = (
            self.project_directory
            / "Media Output"
            / "Validation Evidence"
            / provider_id.strip()
            / session_id.strip()
            / scenario_id.strip()
        )
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{media_id}_{source.name}"
        copy2(source, destination)

        checksum = sha256(destination.read_bytes()).hexdigest()
        relative_path = destination.relative_to(self.project_directory).as_posix()
        media = GeneratedMedia(
            media_id=media_id,
            kind=self._kind_for_suffix(suffix),
            scope=GeneratedMediaScope(
                production_id="PROVIDER-VALIDATION",
                episode_id=session_id.strip(),
                production_task_id=scenario_id.strip(),
                scene_id=criterion_id.strip(),
            ),
            provenance=GeneratedMediaProvenance(
                execution_id=f"VAL-{session_id.strip()}",
                provider_id=provider_id.strip(),
                provider_job_id=f"EXTERNAL-{media_id}",
                attributes=(
                    ("evidence_origin", "externally-rendered-validation-evidence"),
                    ("validation_session_id", session_id.strip()),
                    ("validation_pack_id", pack_id.strip()),
                    ("validation_scenario_id", scenario_id.strip()),
                    ("validation_criterion_id", criterion_id.strip()),
                    ("source_absolute_path", str(source)),
                    ("source_filename", source.name),
                    ("ingested_by", actor.strip()),
                ),
            ),
            file=GeneratedMediaFile(
                relative_path=relative_path,
                checksum_sha256=checksum,
                size_bytes=destination.stat().st_size,
            ),
            technical_metadata=(
                ("validation_evidence", "true"),
                ("source_extension", suffix),
            ),
        )
        self.media_repository.save(media)
        return ValidationEvidenceIngestionResult(media=media, managed_path=destination)

    @staticmethod
    def _kind_for_suffix(suffix: str) -> GeneratedMediaKind:
        if suffix in {".png", ".jpg", ".jpeg"}:
            return GeneratedMediaKind.IMAGE
        return GeneratedMediaKind.VIDEO
