"""Deterministic technical validation for authoritative Generated Media."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from vscs.domain.generated_media import GeneratedMedia, GeneratedMediaState

from .persistence import GeneratedMediaPersistenceService


class GeneratedMediaTechnicalValidationError(RuntimeError):
    """Raised when technical validation cannot be completed safely."""


class TechnicalValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class TechnicalValidationIssue:
    code: str
    message: str
    severity: TechnicalValidationSeverity = TechnicalValidationSeverity.ERROR

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ValueError("technical validation issue code and message are required")


@dataclass(frozen=True, slots=True)
class TechnicalMediaObservation:
    """Provider-neutral measurable facts reported by a technical inspector."""

    relative_path: str
    checksum_sha256: str
    size_bytes: int
    container_format: str | None = None
    video_codec: str | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    duration_seconds: float | None = None
    audio_codec: str | None = None
    audio_channels: int | None = None
    sample_rate_hz: int | None = None
    has_video: bool = False
    has_audio: bool = False

    def __post_init__(self) -> None:
        normalized_path = self.relative_path.strip().replace("\\", "/")
        if not normalized_path:
            raise ValueError("relative_path is required")
        object.__setattr__(self, "relative_path", normalized_path)
        checksum = self.checksum_sha256.strip().lower()
        if len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
            raise ValueError("checksum_sha256 must be hexadecimal SHA-256")
        object.__setattr__(self, "checksum_sha256", checksum)
        if self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")
        for name, value in (
            ("width", self.width),
            ("height", self.height),
            ("audio_channels", self.audio_channels),
            ("sample_rate_hz", self.sample_rate_hz),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive when supplied")
        if self.frame_rate is not None and self.frame_rate <= 0:
            raise ValueError("frame_rate must be positive when supplied")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative")


@dataclass(frozen=True, slots=True)
class GeneratedMediaTechnicalRequirements:
    """Explicit measurable requirements; unspecified fields impose no constraint."""

    allowed_extensions: tuple[str, ...] = ()
    allowed_container_formats: tuple[str, ...] = ()
    allowed_video_codecs: tuple[str, ...] = ()
    allowed_audio_codecs: tuple[str, ...] = ()
    expected_width: int | None = None
    expected_height: int | None = None
    expected_frame_rate: float | None = None
    frame_rate_tolerance: float = 0.01
    minimum_duration_seconds: float | None = None
    maximum_duration_seconds: float | None = None
    require_video: bool | None = None
    require_audio: bool | None = None
    expected_audio_channels: int | None = None
    expected_sample_rate_hz: int | None = None
    minimum_size_bytes: int = 1

    def __post_init__(self) -> None:
        for name, value in (
            ("expected_width", self.expected_width),
            ("expected_height", self.expected_height),
            ("expected_audio_channels", self.expected_audio_channels),
            ("expected_sample_rate_hz", self.expected_sample_rate_hz),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive when supplied")
        if self.expected_frame_rate is not None and self.expected_frame_rate <= 0:
            raise ValueError("expected_frame_rate must be positive when supplied")
        if self.frame_rate_tolerance < 0:
            raise ValueError("frame_rate_tolerance cannot be negative")
        if self.minimum_duration_seconds is not None and self.minimum_duration_seconds < 0:
            raise ValueError("minimum_duration_seconds cannot be negative")
        if self.maximum_duration_seconds is not None and self.maximum_duration_seconds < 0:
            raise ValueError("maximum_duration_seconds cannot be negative")
        if (
            self.minimum_duration_seconds is not None
            and self.maximum_duration_seconds is not None
            and self.minimum_duration_seconds > self.maximum_duration_seconds
        ):
            raise ValueError("minimum_duration_seconds cannot exceed maximum_duration_seconds")
        if self.minimum_size_bytes < 0:
            raise ValueError("minimum_size_bytes cannot be negative")


@dataclass(frozen=True, slots=True)
class GeneratedMediaTechnicalValidationResult:
    media: GeneratedMedia
    observation: TechnicalMediaObservation
    issues: tuple[TechnicalValidationIssue, ...]
    validated_at: datetime
    validator_id: str

    @property
    def passed(self) -> bool:
        return not any(issue.severity is TechnicalValidationSeverity.ERROR for issue in self.issues)


@runtime_checkable
class TechnicalMediaInspector(Protocol):
    def inspect(self, media: GeneratedMedia) -> TechnicalMediaObservation:
        """Inspect one managed Generated Media file without changing authority."""
        ...


class GeneratedMediaTechnicalValidationService:
    """Validate managed media facts and persist audit metadata without granting approval."""

    METADATA_PREFIX = "technical_validation."

    def __init__(
        self,
        persistence: GeneratedMediaPersistenceService,
        inspector: TechnicalMediaInspector,
        *,
        validator_id: str = "vscs:technical-validator",
    ) -> None:
        self.persistence = persistence
        self.inspector = inspector
        self.validator_id = validator_id.strip()
        if not self.validator_id:
            raise ValueError("validator_id cannot be blank")

    def validate(
        self,
        media_id: str,
        requirements: GeneratedMediaTechnicalRequirements,
        *,
        now: datetime | None = None,
    ) -> GeneratedMediaTechnicalValidationResult:
        current = now or datetime.now(UTC)
        media = self.persistence.get(media_id)
        if media is None:
            raise GeneratedMediaTechnicalValidationError(f"Generated Media not found: {media_id}")
        if media.state in {
            GeneratedMediaState.REJECTED,
            GeneratedMediaState.INVALID,
            GeneratedMediaState.SUPERSEDED,
        }:
            raise GeneratedMediaTechnicalValidationError(
                f"Generated Media state is not eligible for technical validation: {media.state.value}"
            )

        observation = self.inspector.inspect(media)
        issues = self._issues(media, observation, requirements)
        updated = self._with_metadata(media, observation, issues, current)
        blocking = tuple(
            issue for issue in issues if issue.severity is TechnicalValidationSeverity.ERROR
        )
        if blocking:
            reason = "; ".join(f"{issue.code}: {issue.message}" for issue in blocking)
            updated = self.persistence.governance.mark_invalid(
                updated,
                actor=self.validator_id,
                reason=f"Technical validation failed: {reason}",
                occurred_at=current,
            )
        updated = self.persistence.save(updated)
        return GeneratedMediaTechnicalValidationResult(
            media=updated,
            observation=observation,
            issues=issues,
            validated_at=current,
            validator_id=self.validator_id,
        )

    @staticmethod
    def _issues(
        media: GeneratedMedia,
        observation: TechnicalMediaObservation,
        requirements: GeneratedMediaTechnicalRequirements,
    ) -> tuple[TechnicalValidationIssue, ...]:
        issues: list[TechnicalValidationIssue] = []
        if observation.relative_path != media.file.relative_path:
            issues.append(
                TechnicalValidationIssue(
                    "managed-path-mismatch",
                    "Technical inspector observed a different path from Generated Media authority.",
                )
            )
        if (
            media.file.checksum_sha256 is not None
            and observation.checksum_sha256 != media.file.checksum_sha256
        ):
            issues.append(
                TechnicalValidationIssue(
                    "checksum-mismatch",
                    "Managed media checksum differs from ingestion authority.",
                )
            )
        if media.file.size_bytes is not None and observation.size_bytes != media.file.size_bytes:
            issues.append(
                TechnicalValidationIssue(
                    "size-mismatch",
                    "Managed media byte size differs from ingestion authority.",
                )
            )
        if observation.size_bytes < requirements.minimum_size_bytes:
            issues.append(
                TechnicalValidationIssue(
                    "file-too-small",
                    f"Media size {observation.size_bytes} is below minimum {requirements.minimum_size_bytes}.",
                )
            )

        suffix = (
            "." + observation.relative_path.rsplit(".", 1)[-1].casefold()
            if "." in observation.relative_path
            else ""
        )
        allowed_extensions = {
            value.casefold() if value.startswith(".") else f".{value.casefold()}"
            for value in requirements.allowed_extensions
        }
        if allowed_extensions and suffix not in allowed_extensions:
            issues.append(
                TechnicalValidationIssue(
                    "extension-not-allowed",
                    f"Media extension {suffix or '<none>'} is not allowed.",
                )
            )
        if requirements.allowed_container_formats and (
            observation.container_format or ""
        ).casefold() not in {value.casefold() for value in requirements.allowed_container_formats}:
            issues.append(
                TechnicalValidationIssue(
                    "container-not-allowed",
                    f"Container format {observation.container_format or '<unknown>'} is not allowed.",
                )
            )
        if requirements.allowed_video_codecs and (observation.video_codec or "").casefold() not in {
            value.casefold() for value in requirements.allowed_video_codecs
        }:
            issues.append(
                TechnicalValidationIssue(
                    "video-codec-not-allowed",
                    f"Video codec {observation.video_codec or '<unknown>'} is not allowed.",
                )
            )
        if requirements.allowed_audio_codecs and (observation.audio_codec or "").casefold() not in {
            value.casefold() for value in requirements.allowed_audio_codecs
        }:
            issues.append(
                TechnicalValidationIssue(
                    "audio-codec-not-allowed",
                    f"Audio codec {observation.audio_codec or '<unknown>'} is not allowed.",
                )
            )

        for code, label, observed, expected in (
            ("width-mismatch", "width", observation.width, requirements.expected_width),
            ("height-mismatch", "height", observation.height, requirements.expected_height),
            (
                "audio-channels-mismatch",
                "audio channels",
                observation.audio_channels,
                requirements.expected_audio_channels,
            ),
            (
                "sample-rate-mismatch",
                "sample rate",
                observation.sample_rate_hz,
                requirements.expected_sample_rate_hz,
            ),
        ):
            if expected is not None and observed != expected:
                issues.append(
                    TechnicalValidationIssue(
                        code,
                        f"Observed {label} {observed!r} does not match expected {expected}.",
                    )
                )
        if requirements.expected_frame_rate is not None and (
            observation.frame_rate is None
            or abs(observation.frame_rate - requirements.expected_frame_rate)
            > requirements.frame_rate_tolerance
        ):
            issues.append(
                TechnicalValidationIssue(
                    "frame-rate-mismatch",
                    f"Observed frame rate {observation.frame_rate!r} does not match expected "
                    f"{requirements.expected_frame_rate} within tolerance "
                    f"{requirements.frame_rate_tolerance}.",
                )
            )
        if requirements.minimum_duration_seconds is not None and (
            observation.duration_seconds is None
            or observation.duration_seconds < requirements.minimum_duration_seconds
        ):
            issues.append(
                TechnicalValidationIssue(
                    "duration-too-short",
                    f"Observed duration {observation.duration_seconds!r} is below minimum "
                    f"{requirements.minimum_duration_seconds}.",
                )
            )
        if requirements.maximum_duration_seconds is not None and (
            observation.duration_seconds is None
            or observation.duration_seconds > requirements.maximum_duration_seconds
        ):
            issues.append(
                TechnicalValidationIssue(
                    "duration-too-long",
                    f"Observed duration {observation.duration_seconds!r} exceeds maximum "
                    f"{requirements.maximum_duration_seconds}.",
                )
            )
        if requirements.require_video is True and not observation.has_video:
            issues.append(
                TechnicalValidationIssue("video-stream-required", "A video stream is required.")
            )
        if requirements.require_video is False and observation.has_video:
            issues.append(
                TechnicalValidationIssue(
                    "video-stream-not-allowed", "A video stream is not allowed."
                )
            )
        if requirements.require_audio is True and not observation.has_audio:
            issues.append(
                TechnicalValidationIssue("audio-stream-required", "An audio stream is required.")
            )
        if requirements.require_audio is False and observation.has_audio:
            issues.append(
                TechnicalValidationIssue(
                    "audio-stream-not-allowed", "An audio stream is not allowed."
                )
            )
        return tuple(
            sorted(issues, key=lambda issue: (issue.severity.value, issue.code, issue.message))
        )

    def _with_metadata(
        self,
        media: GeneratedMedia,
        observation: TechnicalMediaObservation,
        issues: tuple[TechnicalValidationIssue, ...],
        validated_at: datetime,
    ) -> GeneratedMedia:
        retained = tuple(
            (key, value)
            for key, value in media.technical_metadata
            if not key.startswith(self.METADATA_PREFIX)
        )
        blocking = any(issue.severity is TechnicalValidationSeverity.ERROR for issue in issues)
        values: list[tuple[str, str]] = [
            ("technical_validation.status", "failed" if blocking else "passed"),
            ("technical_validation.validator", self.validator_id),
            ("technical_validation.validated_at", validated_at.isoformat()),
            ("technical_validation.checksum_sha256", observation.checksum_sha256),
            ("technical_validation.size_bytes", str(observation.size_bytes)),
            ("technical_validation.has_video", str(observation.has_video).lower()),
            ("technical_validation.has_audio", str(observation.has_audio).lower()),
        ]
        optional = {
            "container_format": observation.container_format,
            "video_codec": observation.video_codec,
            "width": observation.width,
            "height": observation.height,
            "frame_rate": observation.frame_rate,
            "duration_seconds": observation.duration_seconds,
            "audio_codec": observation.audio_codec,
            "audio_channels": observation.audio_channels,
            "sample_rate_hz": observation.sample_rate_hz,
        }
        values.extend(
            (f"technical_validation.{key}", str(value))
            for key, value in optional.items()
            if value is not None
        )
        for index, issue in enumerate(issues, start=1):
            stem = f"technical_validation.issue.{index:03d}"
            values.extend(
                (
                    (f"{stem}.code", issue.code),
                    (f"{stem}.severity", issue.severity.value),
                    (f"{stem}.message", issue.message),
                )
            )
        return replace(media, technical_metadata=(*retained, *values))
