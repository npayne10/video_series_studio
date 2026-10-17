"""Acceptance tests for historical H3 recovery using an isolated temporary project."""

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.application.generated_media import GeneratedMediaPersistenceService
from vscs.application.production_execution import (
    ProductionExecutionError,
    ProviderExecutionReadiness,
    ProviderExecutionReadinessState,
)
from vscs.domain.generated_media import GeneratedMediaState
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository
from vscs.infrastructure.production_execution.execution_profile_store import (
    LocalExecutionProfileStore,
)
from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    LocalComfyUIProductionExecutionBackend,
)
from vscs.infrastructure.production_execution.provider_production_adoption_store import (
    ProviderProductionAdoptionStore,
)


@pytest.fixture
def recovery_case(tmp_path, monkeypatch):
    task = SimpleNamespace(
        task_id="PT-H3-ACCEPTANCE",
        shot_id="EP-001-SCN-001-SHT-003",
        production_id="PRODUCTION",
        episode_id="EP-001",
        scene_id="SCN-001",
    )
    readiness = ProviderExecutionReadiness(
        task_id=task.task_id,
        shot_id=task.shot_id,
        execution_profile="production",
        provider_profile_id="minimax-h3-ref2va-v1",
        provider_profile_fingerprint="b" * 64,
        execution_adapter_id="minimax_h3_automated_execution",
        package_fingerprint="c" * 64,
        timed_span_state="not_applicable",
        span_count=1,
        requirement_count=0,
        approved_keyframe_count=0,
        state=ProviderExecutionReadinessState.READY,
        provider_plan_fingerprint="a" * 64,
        provider_plan_id=f"H3SPANPLAN-{task.shot_id}-AAAAAAAAAAAA",
    )
    backend = object.__new__(LocalComfyUIProductionExecutionBackend)
    backend.project_directory = tmp_path
    backend.managed_media_directory = "Media Output"
    backend._require_task = lambda task_id: task
    backend.package_compilation = SimpleNamespace(
        compile_current=lambda *args, **kwargs: pytest.fail(
            "Historical recovery must never compile current UPD"
        )
    )
    backend.media = GeneratedMediaPersistenceService(
        JsonGeneratedMediaRepository(tmp_path / ".vscs" / "generated_media")
    )
    backend.execution_profiles = LocalExecutionProfileStore(tmp_path)
    backend.provider_policy_registry = SimpleNamespace(
        require=lambda profile_id: SimpleNamespace(provider_id="minimax-h3-ref2va")
    )
    backend.provider_policy_selections = SimpleNamespace(
        selected_profile=lambda task_id, profile: SimpleNamespace(
            profile_id="minimax-h3-ref2va-v1", fingerprint="b" * 64
        )
    )
    backend.provider_production_adoptions = ProviderProductionAdoptionStore(tmp_path)
    backend.provider_production_adoptions.save_readiness(readiness)
    claim = backend._h3_claim_path(task.task_id, "production")
    claim.parent.mkdir(parents=True, exist_ok=True)
    claim.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "task_id": task.task_id,
                "execution_profile": "production",
                "provider_profile_id": "minimax-h3-ref2va-v1",
                "package_fingerprint": readiness.package_fingerprint,
                "plan_fingerprint": readiness.provider_plan_fingerprint,
                "state": "launch_claimed",
            }
        ),
        encoding="utf-8",
    )
    root = (
        tmp_path / ".vscs" / "h3_span_orchestration"
        / task.task_id / readiness.provider_plan_id
    )
    (root / "raw").mkdir(parents=True)
    (root / "normalized").mkdir(parents=True)
    source = root / "normalized" / "span-001.mp4"
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:r=24",
            "-frames:v", "24", "-c:v", "mpeg4", "-y", str(source),
        ],
        check=True,
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    args = {
        "profile": "production",
        "expected_sha256": digest,
        "expected_frame_count": 24,
        "expected_frames_per_second": 24,
    }
    return backend, task, readiness, root, source, claim, args


def test_historical_recovery_end_to_end_and_safe_repeat(recovery_case):
    backend, task, readiness, root, source, claim, args = recovery_case
    original_claim = claim.read_bytes()
    original_source = source.read_bytes()

    first = backend.recover_historical_h3_output_for_profile(task.task_id, **args)

    assert first.state is GeneratedMediaState.GENERATED
    assert dict(first.provenance.attributes)["recovery_kind"] == "historical_h3_evidence_only"
    assert first.file.checksum_sha256 == args["expected_sha256"]
    assert (root / f"{task.shot_id}-governed-h3-assembled.mp4").read_bytes() == original_source
    manifest = json.loads((root / "orchestration.json").read_text(encoding="utf-8"))
    assert manifest["authority_limitation"] == "original_compiled_package_unavailable"
    assert manifest["new_generation_authorized"] is False
    assert backend.provider_production_adoptions.adoption_for(task.task_id, "production")
    assert claim.read_bytes() == original_claim
    assert source.read_bytes() == original_source

    second = backend.recover_historical_h3_output_for_profile(task.task_id, **args)
    assert second.media_id == first.media_id
    assert len(backend.media.list_for_task(task.task_id)) == 1
    assert claim.read_bytes() == original_claim


def test_historical_recovery_conflicting_claim_fails_without_writes(recovery_case):
    backend, task, readiness, root, source, claim, args = recovery_case
    altered = json.loads(claim.read_text(encoding="utf-8"))
    altered["package_fingerprint"] = "0" * 64
    claim.write_text(json.dumps(altered), encoding="utf-8")

    with pytest.raises(ProductionExecutionError, match="disagree"):
        backend.recover_historical_h3_output_for_profile(task.task_id, **args)
    assert not (root / "orchestration.json").exists()
    assert not (root / f"{task.shot_id}-governed-h3-assembled.mp4").exists()
    assert backend.media.list_for_task(task.task_id) == ()


def test_historical_recovery_wrong_checksum_fails_without_writes(recovery_case):
    backend, task, readiness, root, source, claim, args = recovery_case
    args["expected_sha256"] = "0" * 64
    with pytest.raises(ProductionExecutionError, match="SHA-256 mismatch"):
        backend.recover_historical_h3_output_for_profile(task.task_id, **args)
    assert not (root / "orchestration.json").exists()
    assert backend.media.list_for_task(task.task_id) == ()


def test_historical_recovery_conflicting_manifest_blocks_repeat(recovery_case):
    backend, task, readiness, root, source, claim, args = recovery_case
    backend.recover_historical_h3_output_for_profile(task.task_id, **args)
    path = root / "orchestration.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["source_package_fingerprint"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ProductionExecutionError, match="manifest conflicts"):
        backend.recover_historical_h3_output_for_profile(task.task_id, **args)
    assert len(backend.media.list_for_task(task.task_id)) == 1
