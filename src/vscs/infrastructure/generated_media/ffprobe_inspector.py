"""FFprobe-backed technical inspection for managed Generated Media files."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Protocol

from vscs.application.generated_media.technical_validation import (
    GeneratedMediaTechnicalValidationError,
    TechnicalMediaObservation,
)
from vscs.domain.generated_media import GeneratedMedia


class FFprobeRunner(Protocol):
    def run(self, path: Path) -> dict[str, object]:
        """Return decoded ffprobe JSON for one file."""
        ...


@dataclass(frozen=True, slots=True)
class SubprocessFFprobeRunner:
    executable: str = "ffprobe"
    timeout_seconds: float = 30.0

    def run(self, path: Path) -> dict[str, object]:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        command = [
            self.executable,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GeneratedMediaTechnicalValidationError(
                f"Unable to execute ffprobe for {path}: {exc}"
            ) from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "ffprobe failed"
            raise GeneratedMediaTechnicalValidationError(
                f"ffprobe could not inspect {path}: {detail}"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise GeneratedMediaTechnicalValidationError(
                f"ffprobe returned invalid JSON for {path}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise GeneratedMediaTechnicalValidationError("ffprobe response must be a JSON object")
        return {str(key): value for key, value in payload.items()}


@dataclass(slots=True)
class FFprobeGeneratedMediaInspector:
    """Inspect VSCS-managed media using local file integrity plus ffprobe metadata."""

    project_root: Path
    runner: FFprobeRunner = field(default_factory=SubprocessFFprobeRunner)

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()

    def inspect(self, media: GeneratedMedia) -> TechnicalMediaObservation:
        path = self._resolve(media.file.relative_path)
        if not path.exists() or not path.is_file():
            raise GeneratedMediaTechnicalValidationError(
                f"Generated Media file does not exist: {path}"
            )
        checksum, size = _digest(path)
        payload = self.runner.run(path)
        streams_raw = payload.get("streams", [])
        if not isinstance(streams_raw, list):
            raise GeneratedMediaTechnicalValidationError("ffprobe streams must be an array")
        streams = [item for item in streams_raw if isinstance(item, dict)]
        video = next(
            (item for item in streams if str(item.get("codec_type", "")) == "video"),
            None,
        )
        audio = next(
            (item for item in streams if str(item.get("codec_type", "")) == "audio"),
            None,
        )
        format_raw = payload.get("format", {})
        if not isinstance(format_raw, dict):
            raise GeneratedMediaTechnicalValidationError("ffprobe format must be an object")

        return TechnicalMediaObservation(
            relative_path=media.file.relative_path,
            checksum_sha256=checksum,
            size_bytes=size,
            container_format=_optional_text(format_raw.get("format_name")),
            video_codec=_optional_text(video.get("codec_name")) if video is not None else None,
            width=_optional_int(video.get("width")) if video is not None else None,
            height=_optional_int(video.get("height")) if video is not None else None,
            frame_rate=_frame_rate(video) if video is not None else None,
            duration_seconds=_duration(format_raw, streams),
            audio_codec=_optional_text(audio.get("codec_name")) if audio is not None else None,
            audio_channels=_optional_int(audio.get("channels")) if audio is not None else None,
            sample_rate_hz=_optional_int(audio.get("sample_rate")) if audio is not None else None,
            has_video=video is not None,
            has_audio=audio is not None,
        )

    def _resolve(self, relative_path: str) -> Path:
        normalized = relative_path.strip().replace("\\", "/")
        pure = PurePosixPath(normalized)
        if (
            not normalized
            or pure.is_absolute()
            or ".." in pure.parts
            or (pure.parts and ":" in pure.parts[0])
        ):
            raise GeneratedMediaTechnicalValidationError(
                "Generated Media path must remain project-relative"
            )
        candidate = self.project_root.joinpath(*pure.parts).resolve()
        if not candidate.is_relative_to(self.project_root):
            raise GeneratedMediaTechnicalValidationError(
                "Generated Media path escapes configured project root"
            )
        return candidate


def _digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise GeneratedMediaTechnicalValidationError(
            f"Unable to read Generated Media file {path}: {exc}"
        ) from exc
    return digest.hexdigest(), size


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: object) -> int | None:
    if value is None or str(value).strip() in {"", "N/A"}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise GeneratedMediaTechnicalValidationError(
            f"ffprobe value is not an integer: {value!r}"
        ) from exc


def _optional_float(value: object) -> float | None:
    if value is None or str(value).strip() in {"", "N/A"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise GeneratedMediaTechnicalValidationError(
            f"ffprobe value is not numeric: {value!r}"
        ) from exc


def _frame_rate(video: dict[object, object]) -> float | None:
    raw = video.get("avg_frame_rate") or video.get("r_frame_rate")
    if raw is None or str(raw).strip() in {"", "0/0", "N/A"}:
        return None
    try:
        return float(Fraction(str(raw)))
    except (ValueError, ZeroDivisionError) as exc:
        raise GeneratedMediaTechnicalValidationError(
            f"ffprobe frame rate is invalid: {raw!r}"
        ) from exc


def _duration(
    format_raw: dict[object, object],
    streams: list[dict[object, object]],
) -> float | None:
    duration = _optional_float(format_raw.get("duration"))
    if duration is not None:
        return duration
    values = [_optional_float(stream.get("duration")) for stream in streams]
    known = [value for value in values if value is not None]
    return max(known) if known else None
