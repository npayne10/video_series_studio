"""Regression tests for Phase 20.18.2 current-UPD Preview/XPC authority selection."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from vscs.application.governed_reference_plan_source import PersistedGovernedReferencePlanSource
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
)
from vscs.application.production_package import (
    ProductionPackageStatus as CanonicalProductionPackageStatus,
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
from vscs.infrastructure.production_execution.current_authority_backend import (
    CurrentAuthorityLTX23V721ProductionPackageCompilationService,
    _CurrentProductionPackageStore,
    _ProjectDirectoryView,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
)


class _NoReferencePlans:
    def reference_plan_for_shot(self, _shot_id: str):
        return None


def _base_package(*, package_id: str = "PP-SHT-001-BASE") -> ProductionPackage:
    return ProductionPackage(
        package_id=package_id,
        shot_id="SHT-001",
        schema_version="1.0",
        source_fingerprint="planning-source",
        package_fingerprint="base-fingerprint",
        provenance=ProductionPackageProvenance(
            integrated_package_id="IPP-SHT-001",
            integrated_package_fingerprint="integrated-fingerprint",
            planning_review_id="REVIEW-SHT-001",
            planning_review_fingerprint="review-fingerprint",
        ),
        story_context={"shot_id": "SHT-001"},
        shot={"title": "Current authority test"},
        assets=(),
        camera={"production": {"shot_size": "wide", "movement": "static"}},
        lighting={"production": {"lighting_intent": "natural"}},
        environment={"environment_context": "exterior"},
        action_performance={
            "production": {
                "temporal_narrative": "Commander James Spence holds position.",
                "opening_state": "James is standing.",
                "closing_state": "James remains standing.",
            }
        },
        continuity={"production": {}},
        style={"production": {"provider_neutral": True}},
        dialogue=(),
        effects=(),
        references=(),
        universal_description={},
        provider_outputs={},
        validation={
            "action_performance_complete": True,
            "assets_complete": True,
            "camera_complete": True,
            "lighting_complete": True,
            "continuity_complete": True,
            "style_complete": True,
        },
        status=CanonicalProductionPackageStatus.COMPILING,
    )


def _write_packages(root: Path, *packages: ProductionPackage) -> None:
    path = root / "production" / "production_packages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = []
    for package in packages:
        raw = asdict(package)
        raw["status"] = package.status.value
        serialized.append(raw)
    path.write_text(
        json.dumps(
            {"schema_version": "1.0", "production_packages": serialized},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _task(fingerprint: str) -> ProductionTask:
    return ProductionTask(
        task_id="PT-VIDEO-GENERATION-CURRENT-AUTHORITY",
        production_id="TEST",
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


def _plan() -> dict:
    return {
        "schema_version": "1.0",
        "status": "passed",
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx23-local",
            "aspect_tolerance": 0.03,
        },
        "diagnostics": [],
        "references": [
            {
                "reference_id": "REF-JAMES-16X9",
                "asset_id": "CAP-CHR-001",
                "role": "primary_identity",
                "reference_class": "provider_ready_derivative",
                "priority": "required",
                "subject_type": "character",
                "source_path": "references/james-16x9.png",
                "canonical_source_id": "CAP-CHR-001",
                "label": "James governed identity",
                "width": 1672,
                "height": 941,
                "provider_ready": True,
                "provider_profiles": ["production-video-16x9"],
                "coverage": {
                    "framing_type": "full_body",
                    "coverage": "full_required_asset",
                    "required_features_visible": True,
                    "identity_visible": True,
                    "full_required_asset_visible": True,
                },
                "reference_fingerprint": None,
                "file_checksum": "checksum",
                "contains_subjects": [],
                "contains_props": [],
                "contains_environments": [],
            }
        ],
    }


def test_authority_selection_never_falls_back_to_historical_matching_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CurrentAuthorityLTX23V721ProductionPackageCompilationService(tmp_path)
    historical = replace(
        _base_package(package_id="PP-SHT-001-HISTORICAL"),
        universal_description={"production": {"universal_text": "historical"}},
    )
    current = replace(
        _base_package(package_id="PP-SHT-001-CURRENT"),
        universal_description={"production": {"universal_text": "current"}},
    )
    old_fingerprint = service.compiler.authority_fingerprint(historical)
    monkeypatch.setattr(service, "_refresh_current_ready_upd", lambda _task: current)

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match="historical ProductionPackage fallback is prohibited",
    ):
        service._authority_source(_task(old_fingerprint))


def test_ready_upd_reference_dependency_is_refreshed_before_task_authority_check(
    tmp_path: Path,
) -> None:
    base = _base_package()
    _write_packages(tmp_path, base)
    projects = _ProjectDirectoryView(tmp_path)
    packages = _CurrentProductionPackageStore(tmp_path)
    universal = UniversalProductionDescriptionCompilerService(
        projects,  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _NoReferencePlans(),  # type: ignore[arg-type]
    )
    universal.create_from_current_package("SHT-001")
    universal.mark_ready("SHT-001")
    before = packages.require_current_package("SHT-001")
    assert "reference_plan" not in before.universal_description["production"]

    PersistedGovernedReferencePlanSource(projects).save_reference_plan(  # type: ignore[arg-type]
        "SHT-001",
        _plan(),
        provenance={"source": "test"},
    )
    compiler = CurrentAuthorityLTX23V721ProductionPackageCompilationService(tmp_path)
    old_task = _task(compiler.compiler.authority_fingerprint(before))

    refreshed = compiler._refresh_current_ready_upd(old_task)

    assert refreshed.package_id != before.package_id
    production = refreshed.universal_description["production"]
    assert production["reference_plan"]["references"][0]["reference_id"] == ("REF-JAMES-16X9")

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match="approved UPD authority is stale",
    ):
        compiler._authority_source(old_task)
