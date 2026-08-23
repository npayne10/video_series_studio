from pathlib import Path

from vscs.application.provider_capability_validation import ValidationEvidenceIngestionService
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository


def test_external_validation_render_round_trips_through_generated_media(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "render.mp4"
    source.write_bytes(b"external-wan-render")
    repository = JsonGeneratedMediaRepository(project / ".vscs" / "generated_media")
    service = ValidationEvidenceIngestionService(
        project_directory=project,
        media_repository=repository,
    )

    result = service.ingest(
        source_file=source,
        provider_id="wan22-local",
        session_id="WAN22-VAL-001",
        pack_id="wan-2.2-video-v1",
        scenario_id="text-to-video-baseline",
        criterion_id="temporal-coherence",
        actor="validator-1",
    )

    persisted = repository.get(result.media.media_id)
    assert persisted is not None
    assert persisted.file.relative_path.startswith("Media Output/Validation Evidence/wan22-local/")
    assert persisted.provenance.provider_id == "wan22-local"
    assert result.managed_path.exists()
