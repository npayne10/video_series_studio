"""Runtime publication of exact closing Shot Boundary Keyframes for Phase 20.18.2.2i."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

from vscs.application.generated_media import GeneratedMediaPersistenceService
from vscs.application.production_execution import (
    GovernedClosingBoundaryFrame,
    GovernedShotBoundaryError,
    GovernedShotBoundaryStore,
)
from vscs.domain.generated_media import GeneratedMediaKind, GeneratedMediaState


class GovernedShotBoundaryRuntimeError(RuntimeError):
    """Raised when a governed closing boundary cannot be published safely."""


@dataclass(frozen=True, slots=True)
class VideoBoundaryObservation:
    """Technical observation needed to address the exact final governed video frame."""

    frame_count: int
    width: int
    height: int
    frame_rate: str

    @property
    def final_frame_index(self) -> int:
        return self.frame_count - 1


class GovernedShotBoundaryRuntime:
    """Extract and publish exact final frames only from human-approved Generated Media."""

    def __init__(
        self,
        project_directory: Path,
        media: GeneratedMediaPersistenceService,
        *,
        ffmpeg_executable: str | None = None,
        ffprobe_executable: str | None = None,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.media = media
        self.store = GovernedShotBoundaryStore(self.project_directory)
        self.ffmpeg = self._resolve_executable(
            ffmpeg_executable or os.environ.get("VSCS_FFMPEG_EXE"),
            "ffmpeg",
        )
        self.ffprobe = self._resolve_executable(
            ffprobe_executable or os.environ.get("VSCS_FFPROBE_EXE"),
            "ffprobe",
        )

    def publish_closing(
        self,
        media_id: str,
        *,
        published_by: str,
        published_at: datetime | None = None,
    ) -> GovernedClosingBoundaryFrame:
        actor = published_by.strip()
        if not actor:
            raise GovernedShotBoundaryRuntimeError("Closing boundary publication requires a human identity")
        media = self.media.get(media_id.strip())
        if media is None:
            raise GovernedShotBoundaryRuntimeError(f"Generated Media not found: {media_id.strip()}")
        if media.kind is not GeneratedMediaKind.VIDEO:
            raise GovernedShotBoundaryRuntimeError(
                "Only Generated Media video can publish a closing Shot Boundary Keyframe"
            )
        if media.state is not GeneratedMediaState.APPROVED:
            raise GovernedShotBoundaryRuntimeError(
                "Closing Shot Boundary Keyframes may be published only from APPROVED Generated Media"
            )
        shot_id = (media.scope.shot_id or "").strip().upper()
        if not shot_id:
            raise GovernedShotBoundaryRuntimeError(
                "Generated Media has no shot scope for closing boundary publication"
            )

        source = self._project_file(media.file.relative_path)
        source_sha256 = self._sha256(source)
        if media.file.checksum_sha256 is not None and media.file.checksum_sha256 != source_sha256:
            raise GovernedShotBoundaryRuntimeError(
                "Generated Media file checksum changed after authoritative ingestion"
            )

        observation = self._observe_video(source)
        if observation.frame_count <= 0:
            raise GovernedShotBoundaryRuntimeError(
                "Approved Generated Media video exposes no addressable frames"
            )

        digest = hashlib.sha256(
            (
                f"{media.media_id}|{source_sha256}|{observation.final_frame_index}|"
                f"{media.revision}"
            ).encode("utf-8")
        ).hexdigest()[:24].upper()
        boundary_id = f"GBF-{digest}"
        relative_image = (
            Path(".vscs")
            / "governed_shot_boundaries"
            / self._safe_segment(shot_id)
            / f"{boundary_id}.png"
        )
        image = self.project_directory / relative_image

        existing = self.store.current_closing(shot_id)
        if (
            existing is not None
            and existing.boundary_id == boundary_id
            and existing.source_media_sha256 == source_sha256
            and existing.frame_index == observation.final_frame_index
        ):
            try:
                return self.store.require_current_closing(shot_id)
            except GovernedShotBoundaryError:
                pass

        self._extract_frame(source, observation.final_frame_index, image)
        if not image.is_file() or image.stat().st_size <= 0:
            raise GovernedShotBoundaryRuntimeError(
                f"FFmpeg did not create closing boundary image: {image}"
            )
        image_sha256 = self._sha256(image)
        record = GovernedClosingBoundaryFrame(
            boundary_id=boundary_id,
            shot_id=shot_id,
            image_path=relative_image.as_posix(),
            image_sha256=image_sha256,
            source_media_id=media.media_id,
            source_execution_id=media.provenance.execution_id,
            source_media_revision=media.revision,
            source_media_path=media.file.relative_path,
            source_media_sha256=source_sha256,
            frame_index=observation.final_frame_index,
            frame_count=observation.frame_count,
            width=observation.width,
            height=observation.height,
            frame_rate=observation.frame_rate,
            published_by=actor,
            published_at=(published_at or datetime.now(UTC)).isoformat(),
        )
        try:
            return self.store.save(record)
        except GovernedShotBoundaryError as exc:
            raise GovernedShotBoundaryRuntimeError(str(exc)) from exc

    def _observe_video(self, path: Path) -> VideoBoundaryObservation:
        completed = self._run(
            self.ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=width,height,avg_frame_rate,nb_frames,nb_read_frames",
            "-of",
            "json",
            str(path),
            capture_output=True,
        )
        try:
            payload = json.loads(completed.stdout or "{}")
            streams = payload.get("streams", [])
            if not isinstance(streams, list) or len(streams) != 1:
                raise TypeError("expected exactly one selected video stream")
            stream = streams[0]
            if not isinstance(stream, dict):
                raise TypeError("video stream metadata must be an object")
            frame_count = self._positive_int(stream.get("nb_frames")) or self._positive_int(
                stream.get("nb_read_frames")
            )
            width = self._positive_int(stream.get("width"))
            height = self._positive_int(stream.get("height"))
            frame_rate = str(stream.get("avg_frame_rate") or "").strip()
            if frame_count is None or width is None or height is None or not frame_rate:
                raise TypeError("video metadata is incomplete")
            rate = Fraction(frame_rate)
            if rate <= 0:
                raise ValueError("frame rate must be positive")
        except (json.JSONDecodeError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise GovernedShotBoundaryRuntimeError(
                f"FFprobe did not return usable governed-video metadata for {path}"
            ) from exc
        return VideoBoundaryObservation(
            frame_count=frame_count,
            width=width,
            height=height,
            frame_rate=frame_rate,
        )

    def _extract_frame(self, source: Path, frame_index: int, destination: Path) -> None:
        if frame_index < 0:
            raise GovernedShotBoundaryRuntimeError("Closing boundary frame index cannot be negative")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            self.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            f"select=eq(n\\,{frame_index})",
            "-fps_mode",
            "vfr",
            "-frames:v",
            "1",
            str(destination),
        )

    def _project_file(self, relative_path: str) -> Path:
        normalized = relative_path.strip().replace("\\", "/")
        candidate = (self.project_directory / Path(normalized)).resolve(strict=False)
        if not candidate.is_relative_to(self.project_directory):
            raise GovernedShotBoundaryRuntimeError(
                "Generated Media path escapes the configured project"
            )
        if not candidate.is_file():
            raise GovernedShotBoundaryRuntimeError(
                f"Generated Media file does not exist: {candidate}"
            )
        return candidate

    @staticmethod
    def _positive_int(raw: object) -> int | None:
        try:
            value = int(str(raw))
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @staticmethod
    def _safe_segment(value: str) -> str:
        normalized = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in value.strip()
        )
        if not normalized:
            raise GovernedShotBoundaryRuntimeError("Shot boundary path segment is empty")
        return normalized

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise GovernedShotBoundaryRuntimeError(
                f"Unable to read governed media file {path}: {exc}"
            ) from exc
        return digest.hexdigest()

    @staticmethod
    def _resolve_executable(configured: str | None, default_name: str) -> str:
        if configured:
            candidate = Path(configured).expanduser().resolve(strict=False)
            if candidate.is_file():
                return str(candidate)
            resolved = shutil.which(configured)
            if resolved:
                return resolved
            raise GovernedShotBoundaryRuntimeError(
                f"Configured {default_name} executable does not exist: {configured}"
            )
        resolved = shutil.which(default_name)
        if resolved:
            return resolved
        raise GovernedShotBoundaryRuntimeError(
            f"{default_name} is required for governed Shot Boundary Keyframes. "
            f"Put it on PATH or configure VSCS_{default_name.upper()}_EXE."
        )

    @staticmethod
    def _run(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                args,
                check=True,
                text=True,
                capture_output=capture_output,
                timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            command = " ".join(args[:2])
            raise GovernedShotBoundaryRuntimeError(
                f"Shot boundary command failed ({command}): {exc}"
            ) from exc
