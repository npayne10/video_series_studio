"""Tests for Phase 15.3 production asset staging."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.infrastructure.production import (
    AssetStager,
    AssetStagingConfig,
    AssetStagingError,
    StagedAssetKind,
    StagingRequest,
)


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_plan_is_deterministic_and_groups_by_kind(tmp_path: Path) -> None:
    stager = AssetStager(AssetStagingConfig(tmp_path / "staging"))
    requests = (
        StagingRequest("REF-001", StagedAssetKind.REFERENCE, tmp_path / "ref.png"),
        StagingRequest("MODEL-001", StagedAssetKind.MODEL, tmp_path / "model.safetensors"),
    )

    plan = stager.plan("JOB-001", requests)

    assert tuple(item.request.asset_id for item in plan.items) == (
        "MODEL-001",
        "REF-001",
    )
    assert plan.items[0].destination_path == (
        tmp_path / "staging" / "JOB-001" / "model" / "model.safetensors"
    )


def test_plan_rejects_duplicate_ids_and_target_collisions(tmp_path: Path) -> None:
    stager = AssetStager(AssetStagingConfig(tmp_path / "staging"))
    source_a = tmp_path / "a" / "same.bin"
    source_b = tmp_path / "b" / "same.bin"

    with pytest.raises(AssetStagingError, match="Duplicate staging asset ID"):
        stager.plan(
            "JOB-001",
            (
                StagingRequest("ASSET-001", StagedAssetKind.MODEL, source_a),
                StagingRequest("ASSET-001", StagedAssetKind.MODEL, source_b),
            ),
        )

    with pytest.raises(AssetStagingError, match="target collision"):
        stager.plan(
            "JOB-001",
            (
                StagingRequest("ASSET-001", StagedAssetKind.MODEL, source_a),
                StagingRequest("ASSET-002", StagedAssetKind.MODEL, source_b),
            ),
        )


def test_stage_verifies_sources_and_skips_optional_missing_files(tmp_path: Path) -> None:
    source = _write(tmp_path / "sources" / "workflow.json", b"{}")
    stager = AssetStager(AssetStagingConfig(tmp_path / "staging"))
    plan = stager.plan(
        "JOB-001",
        (
            StagingRequest("WORKFLOW-001", StagedAssetKind.WORKFLOW, source),
            StagingRequest(
                "OPTIONAL-001",
                StagedAssetKind.AUDIO,
                tmp_path / "missing.wav",
                required=False,
            ),
        ),
    )

    manifest = stager.stage(plan)

    assert tuple(item.asset_id for item in manifest.artifacts) == ("WORKFLOW-001",)
    artifact = manifest.artifacts[0]
    assert artifact.staged_path.read_bytes() == b"{}"
    stager.validate(manifest)


def test_stage_enforces_expected_checksum(tmp_path: Path) -> None:
    source = _write(tmp_path / "model.bin", b"model-data")
    stager = AssetStager(AssetStagingConfig(tmp_path / "staging"))
    plan = stager.plan(
        "JOB-001",
        (
            StagingRequest(
                "MODEL-001",
                StagedAssetKind.MODEL,
                source,
                expected_checksum="0" * 64,
            ),
        ),
    )

    with pytest.raises(AssetStagingError, match="Source checksum mismatch"):
        stager.stage(plan)


def test_content_cache_is_reused_across_jobs(tmp_path: Path) -> None:
    source = _write(tmp_path / "reference.png", b"reference-data")
    stager = AssetStager(AssetStagingConfig(tmp_path / "staging"))
    request = StagingRequest("REF-001", StagedAssetKind.REFERENCE, source)

    first = stager.stage(stager.plan("JOB-001", (request,)))
    second = stager.stage(stager.plan("JOB-002", (request,)))

    assert first.artifacts[0].cache_reused is False
    assert second.artifacts[0].cache_reused is True
    assert first.artifacts[0].checksum == second.artifacts[0].checksum


def test_manifest_round_trip_validation_and_cleanup(tmp_path: Path) -> None:
    source = _write(tmp_path / "voice.wav", b"audio-data")
    stager = AssetStager(AssetStagingConfig(tmp_path / "staging"))
    manifest = stager.stage(
        stager.plan(
            "JOB-001",
            (StagingRequest("AUDIO-001", StagedAssetKind.AUDIO, source),),
        )
    )

    restored = stager.loads(stager.dumps(manifest))

    assert restored == manifest
    stager.validate(restored)
    tampered = replace(restored, checksum="0" * 64)
    with pytest.raises(AssetStagingError, match="manifest checksum mismatch"):
        stager.validate(tampered)

    stager.cleanup(restored)
    assert restored.staging_directory.exists() is False
    assert stager.config.effective_cache_root.exists() is True


def test_cleanup_refuses_paths_outside_staging_root(tmp_path: Path) -> None:
    stager = AssetStager(AssetStagingConfig(tmp_path / "staging"))
    source = _write(tmp_path / "asset.bin", b"asset")
    manifest = stager.stage(
        stager.plan(
            "JOB-001",
            (StagingRequest("ASSET-001", StagedAssetKind.OTHER, source),),
        )
    )
    unsafe = replace(manifest, staging_directory=tmp_path)

    with pytest.raises(AssetStagingError, match="unsafe staging cleanup"):
        stager.cleanup(unsafe)
