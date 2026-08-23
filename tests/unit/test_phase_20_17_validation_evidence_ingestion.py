from pathlib import Path

from vscs.application.provider_capability_validation import ValidationEvidenceIngestionService
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository


def test_validation_evidence_ingestion_creates_governed_generated_media(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "WAN22-VAL-001.mp4"
    source.write_bytes(b"wan-validation-video")
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
        criterion_id="prompt-adherence",
        actor="validator-1",
    )

    assert result.managed_path.is_file()
    assert result.media.provenance.provider_id == "wan22-local"
    assert repository.get(result.media.media_id) == result.media
    attributes = dict(result.media.provenance.attributes)
    assert attributes["validation_session_id"] == "WAN22-VAL-001"
    assert attributes["validation_scenario_id"] == "text-to-video-baseline"
    assert attributes["validation_criterion_id"] == "prompt-adherence"
    assert attributes["evidence_origin"] == "externally-rendered-validation-evidence"
