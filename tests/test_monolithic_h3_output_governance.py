"""Monolithic H3 output is managed, auditable and never auto-approved."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.application.generated_media import GeneratedMediaPersistenceService
from vscs.application.production_execution import ProductionExecutionError
from vscs.domain.generated_media import GeneratedMediaState
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository
from vscs.infrastructure.production_execution.execution_profile_store import (
    LocalExecutionProfileStore,
)
from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    LocalComfyUIProductionExecutionBackend,
)


def _backend(tmp_path: Path):
    backend = object.__new__(LocalComfyUIProductionExecutionBackend)
    backend.project_directory = tmp_path
    backend.managed_media_directory = "Media Output"
    backend.media = GeneratedMediaPersistenceService(
        JsonGeneratedMediaRepository(tmp_path / ".vscs" / "generated_media")
    )
    backend.execution_profiles = LocalExecutionProfileStore(tmp_path)
    backend.provider_production_adoptions = SimpleNamespace(
        adoption_for=lambda task_id, profile: None
    )
    return backend


def _task():
    return SimpleNamespace(
        task_id="PT-H3-TEST",
        production_id="PRODUCTION",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="EP-001-SCN-001-SHT-003",
    )


def _ready():
    return SimpleNamespace(
        ready_to_execute=True,
        execution_profile="production",
        provider_plan_id="H3SPANPLAN-TEST",
        provider_plan_fingerprint="a" * 64,
        provider_profile_id="minimax-h3-ref2va-v1",
        provider_profile_fingerprint="b" * 64,
        execution_adapter_id="minimax_h3_automated_execution",
        package_fingerprint="c" * 64,
    )


def test_monolithic_h3_output_is_registered_as_managed_unapproved_media(tmp_path):
    backend = _backend(tmp_path)
    raw = tmp_path / "h3-output.mp4"
    raw.write_bytes(b"test-video-output")

    media = backend._register_h3_monolithic_generated_media(
        _task(), readiness=_ready(), final_path=raw, frame_count=240
    )

    assert media.state is GeneratedMediaState.GENERATED
    assert media.file.checksum_sha256 is not None
    assert media.file.relative_path.startswith("Media Output/generated_media/")
    assert (tmp_path / media.file.relative_path).read_bytes() == raw.read_bytes()
    assert media.provenance.provider_job_id == "H3SPANPLAN-TEST"
    assert backend.execution_profiles.profile_for_execution(
        media.provenance.execution_id
    ) == "production"
    assert dict(media.provenance.attributes)["verified_final_frames"] == "240"
    assert len(backend.media.list_for_task(_task().task_id)) == 1

    with pytest.raises(ProductionExecutionError, match="already exists"):
        backend._register_h3_monolithic_generated_media(
            _task(), readiness=_ready(), final_path=raw, frame_count=240
        )


def test_h3_media_registration_rejects_missing_frame_evidence(tmp_path):
    backend = _backend(tmp_path)
    raw = tmp_path / "h3-output.mp4"
    raw.write_bytes(b"test-video-output")

    with pytest.raises(ProductionExecutionError, match="verified frame count"):
        backend._register_h3_monolithic_generated_media(
            _task(), readiness=_ready(), final_path=raw, frame_count=None
        )
    assert backend.media.list_for_task(_task().task_id) == ()


def test_h3_launch_claim_survives_and_rejects_repeated_submission(tmp_path):
    backend = _backend(tmp_path)
    claim = backend._claim_h3_direct_execution(_task(), _ready())
    assert claim.is_file()

    with pytest.raises(ProductionExecutionError, match="durable launch claim"):
        backend._claim_h3_direct_execution(_task(), _ready())


def test_h3_launch_claim_requires_preflight_authority(tmp_path):
    backend = _backend(tmp_path)
    with pytest.raises(ProductionExecutionError, match="READY"):
        backend._claim_h3_direct_execution(
            _task(), SimpleNamespace(ready_to_execute=False)
        )
