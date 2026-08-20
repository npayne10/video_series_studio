from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilationState,
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
from vscs.infrastructure.production_execution import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)


def _source() -> ProductionPackage:
    production = {
        "current_shot_id": "SHT-001",
        "universal_text": (
            "Commander James crosses the Mauritania observation lounge while the camera "
            "tracks laterally. Natural practical lighting remains physically plausible."
        ),
        "story_context": {"purpose": "Reveal the unexplained signal."},
        "shot": {"frame_count": 240, "fps": 24},
        "action_performance": {
            "temporal_narrative": "James walks from the viewport to the console.",
            "performance_direction": "Controlled, observant movement.",
        },
        "assets": [
            {
                "asset_id": "CHR-JAMES",
                "category": "character",
                "canonical_reference": "CAP-CHR-JAMES-FRONT",
            }
        ],
        "camera": {
            "shot_type": "medium-wide",
            "movement": "slow lateral tracking",
            "lens_mm": 35,
        },
        "lighting": {
            "profile": "Mauritania Bridge Operational",
            "key": "soft practical white",
        },
        "environment": {
            "location_asset_id": "LOC-MAURITANIA-OBSERVATION-LOUNGE",
            "atmosphere_state": "controlled",
        },
        "continuity": {
            "previous_approved_final_frame": "continuity/SHT-000-final.png",
            "requirements": ["James remains in standard Guild uniform."],
        },
        "style": {
            "negative_constraints": [
                "no fantasy materials",
                "no excessive holographic glow",
            ]
        },
        "dialogue": [{"speaker": "James", "text": "There it is again."}],
        "effects": [],
        "canonical_references": [
            {
                "asset_id": "CHR-JAMES",
                "canonical_reference": "CAP-CHR-JAMES-FRONT",
            }
        ],
        "source_policy": "approved-production-authority-only",
        "provider_neutral": True,
    }
    universal = {"governed": dict(production), "production": production}
    return ProductionPackage(
        package_id="PP-SHT-001-ABCDEF123456",
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
        story_context=production["story_context"],
        shot=production["shot"],
        assets=tuple(production["assets"]),
        camera=production["camera"],
        lighting=production["lighting"],
        environment=production["environment"],
        action_performance=production["action_performance"],
        continuity=production["continuity"],
        style=production["style"],
        dialogue=tuple(production["dialogue"]),
        effects=(),
        references=tuple(production["canonical_references"]),
        universal_description=universal,
        provider_outputs={},
        validation={
            "action_performance_complete": True,
            "assets_complete": True,
            "camera_complete": True,
            "lighting_complete": True,
            "continuity_complete": True,
            "style_complete": True,
            "universal_description_complete": True,
            "cross_authority_consistent": True,
        },
        status=ProductionPackageStatus.COMPILING,
    )


def _task(source: ProductionPackage) -> ProductionTask:
    authority_fingerprint = ProductionPackageCompilerService.authority_fingerprint(source)
    return ProductionTask(
        task_id="PT-VIDEO-GENERATION-20-15-1",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SHT-001",
            revision=4,
            fingerprint=authority_fingerprint,
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
        json.dumps({"schema_version": "1.0", "production_packages": [data]}, indent=2) + "\n",
        encoding="utf-8",
    )


def test_compiler_carries_governed_camera_lighting_action_continuity_and_references() -> None:
    source = _source()
    task = _task(source)

    compiled = ProductionPackageCompilerService().compile(task, source)

    assert compiled.authority_fingerprint == task.authority.fingerprint
    assert compiled.production_authority["camera"]["movement"] == "slow lateral tracking"
    assert compiled.production_authority["lighting"]["profile"] == "Mauritania Bridge Operational"
    assert compiled.composition_plan["story_context"]["purpose"].startswith("Reveal")
    assert compiled.composition_plan["shot"]["frame_count"] == 240
    assert compiled.composition_plan["action_performance"]["temporal_narrative"].startswith("James")
    assert compiled.composition_plan["canonical_references"][0]["asset_id"] == "CHR-JAMES"
    assert compiled.composition_plan["dialogue"][0]["speaker"] == "James"
    assert compiled.previous_approved_final_frame == "continuity/SHT-000-final.png"
    assert compiled.frame_count == 240
    assert compiled.frames_per_second == 24
    assert "no fantasy materials" in compiled.negative_prompt

    repeated = ProductionPackageCompilerService().compile(task, source)
    assert repeated.package_fingerprint == compiled.package_fingerprint
    assert repeated.seed == compiled.seed


def test_local_compilation_persists_authority_bound_package_and_detects_stale_or_tampered(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = _source()
    task = _task(source)
    _write_source(project, source)
    service = LocalProductionPackageCompilationService(project)

    before = service.status(task)
    assert before.state is ProductionPackageCompilationState.NOT_COMPILED

    compiled = service.compile(task)
    assert compiled.state is ProductionPackageCompilationState.COMPILED
    assert compiled.executable
    assert compiled.path is not None
    raw = json.loads(compiled.path.read_text(encoding="utf-8"))
    assert raw["_vscs_manifest"]["authority_fingerprint"] == task.authority.fingerprint
    assert raw["production_authority"]["camera"]["lens_mm"] == 35
    assert raw["composition_plan"]["continuity"]["requirements"]

    stale_authority = replace(task.authority, fingerprint="different-authority")
    stale_task = replace(task, authority=stale_authority)
    assert service.status(stale_task).state is ProductionPackageCompilationState.STALE

    raw["width"] = 999
    compiled.path.write_text(json.dumps(raw), encoding="utf-8")
    assert service.status(task).state is ProductionPackageCompilationState.INVALID
    with pytest.raises(LocalProductionPackageCompilationError, match="fingerprint"):
        service.validate_file(task, compiled.path)
