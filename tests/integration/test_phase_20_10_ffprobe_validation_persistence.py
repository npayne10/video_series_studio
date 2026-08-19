import hashlib
from datetime import UTC, datetime
from pathlib import Path

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    GeneratedMediaTechnicalRequirements,
    GeneratedMediaTechnicalValidationService,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
    GeneratedMediaState,
)
from vscs.infrastructure.generated_media import (
    FFprobeGeneratedMediaInspector,
    JsonGeneratedMediaRepository,
)

NOW = datetime(2026, 8, 19, 13, 0, tzinfo=UTC)


class FakeFFprobeRunner:
    def run(self, path: Path) -> dict[str, object]:
        assert path.name == "GM-20-10-INTEGRATION.mp4"
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "24/1",
                    "duration": "10.0",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": "48000",
                    "duration": "10.0",
                },
            ],
            "format": {
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "duration": "10.0",
            },
        }


def test_phase_20_10_managed_media_validation_survives_repository_restart(tmp_path) -> None:
    project_root = tmp_path / "project"
    relative = "generated_media/XORIX/EP-001/PT-20-10-001/GM-20-10-INTEGRATION.mp4"
    path = project_root / relative
    path.parent.mkdir(parents=True)
    payload = b"phase-20-10-managed-media"
    path.write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()

    repository_root = tmp_path / "media-records"
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(repository_root))
    persistence.register(
        GeneratedMedia(
            media_id="GM-20-10-INTEGRATION",
            kind=GeneratedMediaKind.VIDEO,
            scope=GeneratedMediaScope(
                production_id="XORIX",
                episode_id="EP-001",
                production_task_id="PT-20-10-001",
            ),
            provenance=GeneratedMediaProvenance(
                execution_id="PEX-20-10-INTEGRATION",
                provider_id="LOCAL-COMFYUI-01",
                provider_job_id="prompt-20-10-integration",
            ),
            file=GeneratedMediaFile(
                relative_path=relative,
                checksum_sha256=checksum,
                size_bytes=len(payload),
            ),
        )
    )

    inspector = FFprobeGeneratedMediaInspector(project_root, runner=FakeFFprobeRunner())
    service = GeneratedMediaTechnicalValidationService(persistence, inspector)
    result = service.validate(
        "GM-20-10-INTEGRATION",
        GeneratedMediaTechnicalRequirements(
            allowed_extensions=("mp4",),
            allowed_video_codecs=("h264",),
            allowed_audio_codecs=("aac",),
            expected_width=1920,
            expected_height=1080,
            expected_frame_rate=24.0,
            minimum_duration_seconds=9.9,
            maximum_duration_seconds=10.1,
            require_video=True,
            require_audio=True,
            expected_audio_channels=2,
            expected_sample_rate_hz=48000,
        ),
        now=NOW,
    )

    assert result.passed
    assert result.media.state is GeneratedMediaState.GENERATED
    assert result.observation.frame_rate == 24.0
    assert result.observation.duration_seconds == 10.0

    restarted = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(repository_root))
    restored = restarted.get("GM-20-10-INTEGRATION")
    assert restored is not None
    assert restored.state is GeneratedMediaState.GENERATED
    metadata = dict(restored.technical_metadata)
    assert metadata["technical_validation.status"] == "passed"
    assert metadata["technical_validation.video_codec"] == "h264"
    assert metadata["technical_validation.audio_codec"] == "aac"
    assert metadata["technical_validation.checksum_sha256"] == checksum
