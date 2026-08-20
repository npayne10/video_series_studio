from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from vscs.application.production_execution.package_compilation import ProductionPackageCompilerService
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)


def _source(reference: str, checksum: str) -> ProductionPackage:
    production = {
        "universal_text": "James and Sandra work on the bridge with Xorix visible ahead.",
        "shot": {
            "target_runtime_seconds": 22,
            "production_objective": "Preserve both canonical characters on the bridge.",
        },
        "assets": [
            {
                "asset_id": "CAP-CHR-001",
                "category": "character",
                "role": "Commander James Spence",
                "canonical_reference": reference,
                "canonical_references": [
                    {"file_path": reference, "checksum": checksum, "role": "primary"}
                ],
            }
        ],
        "canonical_references": [
            {"asset_id": "CAP-CHR-001", "canonical_reference": reference}
        ],
        "camera": {"shot_size": "medium_close", "movement": "static"},
        "lighting": {"lighting_intent": "low_key", "color_temperature_k": 4300},
        "environment": {"environment_context": "ship_bridge"},
        "continuity": {},
        "style": {},
        "action_performance": {},
        "dialogue": [],
        "effects": [],
        "source_policy": "approved-production-authority-only",
        "provider_neutral": True,
    }
    universal = {"governed": dict(production), "production": production}
    return ProductionPackage(
        package_id="PP-SHT-001-READY",
        shot_id="SHT-001",
        schema_version="1.0",
        source_fingerprint="source",
        package_fingerprint="package",
        provenance=ProductionPackageProvenance(
            integrated_package_id="IPP-SHT-001",
            integrated_package_fingerprint="integrated",
            planning_review_id="REVIEW-SHT-001",
            planning_review_fingerprint="review",
        ),
        story_context={},
        shot=production["shot"],
        assets=tuple(production["assets"]),
        camera=production["camera"],
        lighting=production["lighting"],
        environment=production["environment"],
        action_performance={},
        continuity={},
        style={},
        dialogue=(),
        effects=(),
        references=tuple(production["canonical_references"]),
        universal_description=universal,
        provider_outputs={},
        validation={
            "universal_description_complete": True,
            "cross_authority_consistent": True,
        },
        status=ProductionPackageStatus.COMPILING,
    )


def _task(source: ProductionPackage) -> ProductionTask:
    return ProductionTask(
        task_id="PT-VIDEO-GENERATION-20-15-1A",
        production_id="VSCS TEST",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SHT-001",
            revision=1,
            fingerprint=ProductionPackageCompilerService.authority_fingerprint(source),
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=ProductionTaskState.READY,
    )


def _write_source(project: Path, source: ProductionPackage) -> None:
    data = asdict(source)
    data["status"] = source.status.value
    path = project / "production" / "production_packages.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"schema_version": "1.0", "production_packages": [data]}, indent=2),
        encoding="utf-8",
    )


def test_target_runtime_drives_frame_count_when_no_explicit_frames(tmp_path: Path) -> None:
    asset = tmp_path / "asset.png"
    asset.write_bytes(b"canonical")
    source = _source(str(asset), hashlib.sha256(b"canonical").hexdigest())

    compiled = ProductionPackageCompilerService().compile(_task(source), source)

    assert compiled.frames_per_second == 24
    assert compiled.duration_seconds == 22
    assert compiled.frame_count == 528
    assert "wrong canonical asset identity" in compiled.negative_prompt
    assert "authoritative identity definitions" in compiled.positive_prompt


def test_local_compiler_resolves_visual_asset_and_builds_reference_plan(tmp_path: Path) -> None:
    project = tmp_path / "project"
    asset = project / "assets" / "characters" / "CAP-CHR-001-Master-V1.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"canonical-james")
    relative = "assets/characters/CAP-CHR-001-Master-V1.png"
    checksum = hashlib.sha256(b"canonical-james").hexdigest()
    source = _source(relative, checksum)
    task = _task(source)
    _write_source(project, source)

    status = LocalProductionPackageCompilationService(project).compile(task)

    assert status.path is not None
    raw = json.loads(status.path.read_text(encoding="utf-8"))
    resolved = raw["resolved_visual_assets"][0]
    assert Path(resolved["resolved_source_path"]) == asset.resolve(strict=False)
    assert resolved["checksum"] == checksum
    assert raw["reference_plan"]["identity_references"][0]["asset_id"] == "CAP-CHR-001"
    assert raw["reference_plan"]["identity_references"][0]["delivery"] == "ic_lora"
    assert raw["timing"] == {"duration_seconds": 22.0, "fps": 24, "frames": 528}
    assert raw["generation"]["seed"] == raw["seed"]
    assert raw["output"]["filename_prefix"] == raw["filename_prefix"]
    assert raw["composition_plan"]["provider_ready"] is True
    assert raw["_vscs_manifest"]["compiler"] == "VSCS Phase 20.15.1a"


def test_local_compiler_blocks_missing_required_canonical_reference(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = _source(
        "assets/characters/CAP-CHR-001-Master-V1.png",
        hashlib.sha256(b"missing").hexdigest(),
    )
    task = _task(source)
    _write_source(project, source)

    with pytest.raises(LocalProductionPackageCompilationError, match="does not exist"):
        LocalProductionPackageCompilationService(project).compile(task)


def test_local_compiler_blocks_canonical_checksum_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    asset = project / "assets" / "characters" / "CAP-CHR-001-Master-V1.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"canonical-james")
    source = _source(
        "assets/characters/CAP-CHR-001-Master-V1.png",
        hashlib.sha256(b"different").hexdigest(),
    )
    task = _task(source)
    _write_source(project, source)

    with pytest.raises(LocalProductionPackageCompilationError, match="checksum mismatch"):
        LocalProductionPackageCompilationService(project).compile(task)
