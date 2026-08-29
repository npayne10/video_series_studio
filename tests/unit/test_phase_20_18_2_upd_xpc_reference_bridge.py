"""Cross-layer acceptance for the UPD -> XPC governed reference-plan bridge."""

from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path

from vscs.application.production_execution.package_compilation import (
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
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
)


def _png(path: Path, width: int, height: int) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    raw = (b"\x00" + (b"\x00\x00\x00" * width)) * height
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 1))
        + chunk(b"IEND", b"")
    )


def _governed_description() -> dict[str, object]:
    return {
        "current_shot_id": "SHT-001",
        "universal_text": "Commander James Spence holds position in the observation lounge.",
        "story_context": {},
        "shot": {"frame_count": 145, "fps": 24},
        "action_performance": {},
        "assets": [],
        "camera": {},
        "lighting": {},
        "environment": {},
        "continuity": {},
        "style": {},
        "dialogue": [],
        "effects": [],
        "canonical_references": [],
        "consistency_findings": [],
        "source_policy": "approved-production-authority-only",
        "provider_neutral": True,
        "reference_plan": {
            "schema_version": "1.0",
            "target": {
                "width": 1280,
                "height": 720,
                "profile_id": "production-video-16x9",
                "provider_id": "ltx23-local",
                "aspect_tolerance": 0.03,
            },
            "references": [
                {
                    "reference_id": "REF-JAMES-VIDEO-IDENTITY",
                    "asset_id": "CAP-CHR-001",
                    "role": "primary_identity",
                    "reference_class": "provider_ready_derivative",
                    "priority": "required",
                    "subject_type": "character",
                    "source_path": "references/james-video-identity.png",
                    "canonical_source_id": "CAP-CHR-001-MASTER",
                    "label": "James Spence Video Identity 16:9",
                    "width": 1024,
                    "height": 1536,
                    "provider_ready": True,
                    "provider_profiles": ["production-video-16x9"],
                    "coverage": {
                        "framing_type": "full_body",
                        "coverage": "full_required_asset",
                        "required_features_visible": True,
                        "identity_visible": True,
                        "full_required_asset_visible": True,
                    },
                    "reference_fingerprint": "stale-reference-fingerprint",
                    "file_checksum": "stale-file-checksum",
                    "contains_subjects": ["James Spence"],
                    "contains_props": [],
                    "contains_environments": [],
                }
            ],
        },
    }


def _source(compiled_upd: dict[str, object]) -> ProductionPackage:
    return ProductionPackage(
        package_id="PP-SHT-001-UPD",
        shot_id="SHT-001",
        schema_version="1.0",
        source_fingerprint="planning-source",
        package_fingerprint="upd-source-fingerprint",
        provenance=ProductionPackageProvenance(
            integrated_package_id="IPP-SHT-001",
            integrated_package_fingerprint="integrated-fingerprint",
            planning_review_id="REVIEW-SHT-001",
            planning_review_fingerprint="review-fingerprint",
        ),
        story_context={},
        shot={},
        assets=(),
        camera={},
        lighting={},
        environment={},
        action_performance={},
        continuity={},
        style={},
        dialogue=(),
        effects=(),
        references=(),
        universal_description=compiled_upd,
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
        task_id="PT-UPD-XPC-BRIDGE",
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


def test_upd_reference_plan_contract_reaches_xpc_and_refreshes_real_file_facts(
    tmp_path: Path,
) -> None:
    image = tmp_path / "references" / "james-video-identity.png"
    _png(image, 1280, 720)

    compiled_upd = UniversalProductionDescriptionCompilerService._compile_description(
        _governed_description()
    )
    production = compiled_upd["production"]
    assert production["reference_plan"]["references"][0]["role"] == "primary_identity"

    source = _source(compiled_upd)
    compiled = ProductionPackageCompilerService(reference_root=tmp_path).compile(
        _task(source), source
    )

    assert compiled.reference_plan is not None
    assert compiled.reference_plan["status"] == "passed"
    governed = compiled.reference_plan["references"][0]
    assert governed["reference_id"] == "REF-JAMES-VIDEO-IDENTITY"
    assert governed["role"] == "primary_identity"
    assert governed["width"] == 1280
    assert governed["height"] == 720
    assert governed["file_checksum"] == hashlib.sha256(image.read_bytes()).hexdigest()
    assert governed["file_checksum"] != "stale-file-checksum"
    assert governed["reference_fingerprint"] != "stale-reference-fingerprint"
    assert compiled.composition_plan["reference_plan"] == compiled.reference_plan
