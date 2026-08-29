from __future__ import annotations

import hashlib
import json
import struct
import zlib
from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilationError,
    ProductionPackageCompilerService,
)
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
from vscs.infrastructure.production_execution import LocalProductionPackageCompilationService


def _png(path: Path, width: int, height: int, *, marker: bytes = b"x") -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    raw_row = b"\x00" + (b"\x00\x00\x00" * width)
    raw = raw_row * height
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"tEXt", b"vscs=" + marker)
        + chunk(b"IDAT", zlib.compress(raw, 1))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _reference(
    reference_id: str,
    role: str,
    path: str,
    *,
    asset_id: str | None = "CAP-CHR-001",
    priority: str = "required",
    full_asset: bool = True,
    width: int = 1,
    height: int = 1,
) -> dict[str, object]:
    return {
        "reference_id": reference_id,
        "role": role,
        "reference_class": (
            "shot_composite" if role == "scene_composition_anchor" else "provider_ready_derivative"
        ),
        "priority": priority,
        "subject_type": (
            "multi_subject_scene" if role == "scene_composition_anchor" else "character"
        ),
        "source_path": path,
        "canonical_source_id": f"{asset_id}-MASTER" if asset_id else None,
        "asset_id": asset_id,
        "width": width,
        "height": height,
        "provider_ready": True,
        "provider_profiles": ["production-video-16x9"],
        "file_checksum": "stale-checksum",
        "coverage": {
            "framing_type": "full_body",
            "coverage": "full_body",
            "required_features_visible": True,
            "identity_visible": True,
            "full_required_asset_visible": full_asset,
        },
    }


def _source(reference_plan: dict[str, object] | None = None) -> ProductionPackage:
    production: dict[str, object] = {
        "current_shot_id": "SHT-001",
        "universal_text": "Commander James crosses the Mauritania observation lounge.",
        "story_context": {"purpose": "Reveal the unexplained signal."},
        "shot": {"frame_count": 121, "fps": 25},
        "assets": [{"asset_id": "CAP-CHR-001", "category": "character"}],
        "camera": {"shot_type": "medium-wide", "lens_mm": 35},
        "lighting": {"profile": "Mauritania Operational"},
        "environment": {"location_asset_id": "LOC-MAURITANIA-LOUNGE"},
        "action_performance": {"temporal_narrative": "James walks to the console."},
        "continuity": {},
        "style": {"negative_constraints": ["identity drift"]},
        "dialogue": [],
        "effects": [],
        "canonical_references": [],
        "render": {"width": 1280, "height": 720},
        "provider_neutral": True,
    }
    if reference_plan is not None:
        production["reference_plan"] = reference_plan
    universal = {"governed": dict(production), "production": production}
    return ProductionPackage(
        package_id="PP-SHT-001-XPC",
        shot_id="SHT-001",
        schema_version="1.0",
        source_fingerprint="planning-source",
        package_fingerprint="canonical-package-fingerprint",
        provenance=ProductionPackageProvenance(
            integrated_package_id="IPP-SHT-001",
            integrated_package_fingerprint="integrated-fingerprint",
            planning_review_id="REVIEW-SHT-001",
            planning_review_fingerprint="review-fingerprint",
        ),
        story_context=dict(production["story_context"]),
        shot=dict(production["shot"]),
        assets=tuple(dict(item) for item in production["assets"]),
        camera=dict(production["camera"]),
        lighting=dict(production["lighting"]),
        environment=dict(production["environment"]),
        action_performance=dict(production["action_performance"]),
        continuity={},
        style=dict(production["style"]),
        dialogue=(),
        effects=(),
        references=(),
        universal_description=universal,
        provider_outputs={},
        validation={
            "universal_description_complete": True,
            "cross_authority_consistent": True,
        },
        status=ProductionPackageStatus.COMPILING,
    )


def _task(source: ProductionPackage) -> ProductionTask:
    fingerprint = ProductionPackageCompilerService.authority_fingerprint(source)
    return ProductionTask(
        task_id="PT-XPC-GOVERNED-REF",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SHT-001",
            revision=1,
            fingerprint=fingerprint,
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=ProductionTaskState.READY,
    )


def _plan(*references: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx23-local",
        },
        "references": list(references),
    }


def _write_source(project: Path, source: ProductionPackage) -> None:
    from dataclasses import asdict

    raw = asdict(source)
    raw["status"] = source.status.value
    path = project / "production" / "production_packages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": "1.0", "production_packages": [raw]}, indent=2) + "\n",
        encoding="utf-8",
    )


def test_xpc_refreshes_real_dimensions_checksum_and_fingerprint(tmp_path: Path) -> None:
    relative = Path("references") / "james.png"
    image = tmp_path / relative
    _png(image, 1280, 720, marker=b"first")
    source = _source(_plan(_reference("REF-JAMES", "primary_identity", str(relative))))
    task = _task(source)
    compiler = ProductionPackageCompilerService(reference_root=tmp_path)

    first = compiler.compile(task, source)

    assert first.reference_plan is not None
    governed = first.reference_plan["references"][0]
    assert governed["width"] == 1280
    assert governed["height"] == 720
    assert governed["file_checksum"] == hashlib.sha256(image.read_bytes()).hexdigest()
    assert governed["file_checksum"] != "stale-checksum"
    assert governed["reference_fingerprint"]
    assert first.composition_plan["reference_plan"] == first.reference_plan

    first_package_fingerprint = first.package_fingerprint
    _png(image, 1280, 720, marker=b"changed-file-content")
    second = compiler.compile(task, source)
    assert second.reference_plan is not None
    assert second.reference_plan["references"][0]["file_checksum"] != governed["file_checksum"]
    assert second.package_fingerprint != first_package_fingerprint


def test_xpc_blocks_portrait_reference_against_16x9_target(tmp_path: Path) -> None:
    image = tmp_path / "references" / "james-portrait.png"
    _png(image, 1024, 1536)
    source = _source(
        _plan(_reference("REF-JAMES", "primary_identity", "references/james-portrait.png"))
    )

    with pytest.raises(ProductionPackageCompilationError, match="REFERENCE_ASPECT_MISMATCH"):
        ProductionPackageCompilerService(reference_root=tmp_path).compile(_task(source), source)


def test_xpc_blocks_required_reference_extrapolation_risk(tmp_path: Path) -> None:
    image = tmp_path / "references" / "james-cropped.png"
    _png(image, 1280, 720)
    source = _source(
        _plan(
            _reference(
                "REF-JAMES-CROPPED",
                "primary_identity",
                "references/james-cropped.png",
                full_asset=False,
            )
        )
    )

    with pytest.raises(ProductionPackageCompilationError, match="REFERENCE_EXTRAPOLATION_RISK"):
        ProductionPackageCompilerService(reference_root=tmp_path).compile(_task(source), source)


def test_xpc_preserves_multi_reference_roles_and_order(tmp_path: Path) -> None:
    entries = (
        ("REF-ROOM", "scene_composition_anchor", None),
        ("REF-JAMES", "primary_identity", "CAP-CHR-001"),
        ("REF-CHERYL", "secondary_identity", "CAP-CHR-002"),
        ("REF-ROS", "secondary_identity", "CAP-CHR-003"),
    )
    references = []
    for reference_id, role, asset_id in entries:
        relative = f"references/{reference_id}.png"
        _png(tmp_path / relative, 1280, 720)
        references.append(_reference(reference_id, role, relative, asset_id=asset_id))
    source = _source(_plan(*references))

    compiled = ProductionPackageCompilerService(reference_root=tmp_path).compile(
        _task(source), source
    )

    assert compiled.reference_plan is not None
    assert [item["reference_id"] for item in compiled.reference_plan["references"]] == [
        item[0] for item in entries
    ]
    assert [item["role"] for item in compiled.reference_plan["references"]] == [
        item[1] for item in entries
    ]
    assert compiled.reference_plan["status"] == "passed"


def test_xpc_blocks_missing_real_reference_file(tmp_path: Path) -> None:
    source = _source(
        _plan(_reference("REF-JAMES", "primary_identity", "references/not-there.png"))
    )

    with pytest.raises(ProductionPackageCompilationError, match="REFERENCE_FILE_MISSING"):
        ProductionPackageCompilerService(reference_root=tmp_path).compile(_task(source), source)


def test_xpc_keeps_legacy_package_without_reference_plan_backward_compatible() -> None:
    source = _source()
    compiled = ProductionPackageCompilerService().compile(_task(source), source)

    assert compiled.reference_plan is None
    assert "reference_plan" not in compiled.composition_plan
    assert "reference_plan" not in compiled.to_dict()


def test_local_xpc_persists_compiled_governed_reference_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    relative = Path("references") / "james.png"
    image = project / relative
    _png(image, 1280, 720)
    source = _source(_plan(_reference("REF-JAMES", "primary_identity", str(relative))))
    task = _task(source)
    _write_source(project, source)

    status = LocalProductionPackageCompilationService(project).compile(task)

    assert status.executable
    assert status.path is not None
    raw = json.loads(status.path.read_text(encoding="utf-8"))
    assert raw["_vscs_manifest"]["compiler"] == "VSCS Phase 20.18.2"
    assert raw["reference_plan"]["status"] == "passed"
    assert raw["reference_plan"]["references"][0]["width"] == 1280
    assert raw["reference_plan"]["references"][0]["height"] == 720
    assert raw["reference_plan"]["references"][0]["file_checksum"] == hashlib.sha256(
        image.read_bytes()
    ).hexdigest()
