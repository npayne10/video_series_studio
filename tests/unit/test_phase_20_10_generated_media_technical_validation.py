from datetime import UTC, datetime

import pytest

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    GeneratedMediaTechnicalRequirements,
    GeneratedMediaTechnicalValidationError,
    GeneratedMediaTechnicalValidationService,
    TechnicalMediaObservation,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
    GeneratedMediaState,
)

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
CHECKSUM = "a" * 64


class MemoryRepository:
    def __init__(self, media: GeneratedMedia) -> None:
        self.records = {media.media_id: media}

    def get(self, media_id: str) -> GeneratedMedia | None:
        return self.records.get(media_id)

    def save(self, media: GeneratedMedia) -> GeneratedMedia:
        self.records[media.media_id] = media
        return media

    def list_for_production(self, production_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item for item in self.records.values() if item.scope.production_id == production_id
        )

    def list_for_episode(self, production_id: str, episode_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_production(production_id)
            if item.scope.episode_id == episode_id
        )

    def list_for_scene(
        self, production_id: str, episode_id: str, scene_id: str
    ) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_episode(production_id, episode_id)
            if item.scope.scene_id == scene_id
        )

    def list_for_shot(
        self, production_id: str, episode_id: str, scene_id: str, shot_id: str
    ) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_scene(production_id, episode_id, scene_id)
            if item.scope.shot_id == shot_id
        )

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.records.values()
            if item.scope.production_task_id == production_task_id
        )

    def list_for_execution(self, execution_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item for item in self.records.values() if item.provenance.execution_id == execution_id
        )


class FixedInspector:
    def __init__(self, observation: TechnicalMediaObservation) -> None:
        self.observation = observation
        self.calls = 0

    def inspect(self, media: GeneratedMedia) -> TechnicalMediaObservation:
        self.calls += 1
        return self.observation


def _media() -> GeneratedMedia:
    return GeneratedMedia(
        media_id="GM-20-10-001",
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="XORIX",
            episode_id="EP-001",
            production_task_id="PT-20-10-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id="PEX-20-10-001",
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id="prompt-20-10-001",
        ),
        file=GeneratedMediaFile(
            relative_path="generated_media/XORIX/EP-001/PT-20-10-001/media.mp4",
            checksum_sha256=CHECKSUM,
            size_bytes=2048,
        ),
    )


def _observation(**changes: object) -> TechnicalMediaObservation:
    values: dict[str, object] = {
        "relative_path": "generated_media/XORIX/EP-001/PT-20-10-001/media.mp4",
        "checksum_sha256": CHECKSUM,
        "size_bytes": 2048,
        "container_format": "mov,mp4,m4a,3gp,3g2,mj2",
        "video_codec": "h264",
        "width": 1920,
        "height": 1080,
        "frame_rate": 24.0,
        "duration_seconds": 10.0,
        "audio_codec": "aac",
        "audio_channels": 2,
        "sample_rate_hz": 48000,
        "has_video": True,
        "has_audio": True,
    }
    values.update(changes)
    return TechnicalMediaObservation(**values)  # type: ignore[arg-type]


def _requirements() -> GeneratedMediaTechnicalRequirements:
    return GeneratedMediaTechnicalRequirements(
        allowed_extensions=(".mp4",),
        allowed_video_codecs=("h264",),
        expected_width=1920,
        expected_height=1080,
        expected_frame_rate=24.0,
        minimum_duration_seconds=9.5,
        maximum_duration_seconds=10.5,
        require_video=True,
        require_audio=True,
        expected_audio_channels=2,
        expected_sample_rate_hz=48000,
    )


def test_pass_persists_measurements_without_advancing_governance() -> None:
    repository = MemoryRepository(_media())
    inspector = FixedInspector(_observation())
    service = GeneratedMediaTechnicalValidationService(
        GeneratedMediaPersistenceService(repository), inspector
    )

    result = service.validate("GM-20-10-001", _requirements(), now=NOW)

    assert result.passed
    assert result.media.state is GeneratedMediaState.GENERATED
    metadata = dict(result.media.technical_metadata)
    assert metadata["technical_validation.status"] == "passed"
    assert metadata["technical_validation.width"] == "1920"
    assert metadata["technical_validation.frame_rate"] == "24.0"
    assert metadata["technical_validation.validator"] == "vscs:technical-validator"
    assert result.media.governance_history == ()


def test_blocking_failure_marks_media_invalid_with_audit_event() -> None:
    repository = MemoryRepository(_media())
    service = GeneratedMediaTechnicalValidationService(
        GeneratedMediaPersistenceService(repository),
        FixedInspector(_observation(width=1280, has_audio=False)),
    )

    result = service.validate("GM-20-10-001", _requirements(), now=NOW)

    assert not result.passed
    assert result.media.state is GeneratedMediaState.INVALID
    assert {issue.code for issue in result.issues} == {"audio-stream-required", "width-mismatch"}
    assert result.media.governance_history[-1].actor == "vscs:technical-validator"
    assert "Technical validation failed" in result.media.governance_history[-1].reason
    assert dict(result.media.technical_metadata)["technical_validation.status"] == "failed"


def test_checksum_mismatch_is_blocking_even_when_stream_properties_pass() -> None:
    repository = MemoryRepository(_media())
    service = GeneratedMediaTechnicalValidationService(
        GeneratedMediaPersistenceService(repository),
        FixedInspector(_observation(checksum_sha256="b" * 64)),
    )

    result = service.validate("GM-20-10-001", _requirements(), now=NOW)

    assert not result.passed
    assert any(issue.code == "checksum-mismatch" for issue in result.issues)
    assert result.media.state is GeneratedMediaState.INVALID


def test_frame_rate_tolerance_is_explicit() -> None:
    repository = MemoryRepository(_media())
    service = GeneratedMediaTechnicalValidationService(
        GeneratedMediaPersistenceService(repository),
        FixedInspector(_observation(frame_rate=23.976)),
    )

    result = service.validate(
        "GM-20-10-001",
        GeneratedMediaTechnicalRequirements(expected_frame_rate=24.0, frame_rate_tolerance=0.05),
        now=NOW,
    )

    assert result.passed


def test_terminal_invalid_media_cannot_be_revalidated() -> None:
    repository = MemoryRepository(_media())
    persistence = GeneratedMediaPersistenceService(repository)
    failed_service = GeneratedMediaTechnicalValidationService(
        persistence,
        FixedInspector(_observation(width=1280)),
    )
    failed_service.validate("GM-20-10-001", _requirements(), now=NOW)

    with pytest.raises(GeneratedMediaTechnicalValidationError, match="not eligible"):
        GeneratedMediaTechnicalValidationService(
            persistence,
            FixedInspector(_observation()),
        ).validate("GM-20-10-001", _requirements(), now=NOW)
