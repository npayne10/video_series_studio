"""Q3.1.3.5.3 persisted-source to real compiler fail-closed acceptance.

Every filesystem is an isolated pytest tmp_path. No provider or production output runs.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from vscs.application.production_package import ProductionPackageService
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository
from vscs.infrastructure.production_execution.h3_persisted_authority_gate import (
    H3PersistedAuthoritySource,
)

from vscs.infrastructure.production_execution.h3_persisted_authority_gate import (
    verify_persisted_h3_reference_authority,
)
from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceGovernanceError,
)

def _write_records(project, *, source_id="PKG-TEST", task_shot="SHT-TEST"):
    task_root = project / "production" / "scheduling" / "tasks"
    task_root.mkdir(parents=True, exist_ok=True)
    task = {
        "task_id": "TASK-TEST",
        "production_id": "PROD-TEST",
        "episode_id": "EP-TEST",
        "scene_id": "SCN-TEST",
        "shot_id": task_shot,
        "task_type": "video_generation",
        "capabilities": ["video_generation"],
        "expected_outputs": ["generated_video"],
        "state": "ready",
        "authority": {
            "authority_type": "universal_production_description",
            "authority_id": "AUTH-TEST",
            "revision": 1,
            "fingerprint": "authority-fingerprint",
            "approved": True,
            "approved_by": "test-operator",
        },
        "created_at": "2026-10-01T12:00:00+00:00",
    }
    task_path = task_root / "TASK-TEST.json"
    task_path.write_text(json.dumps({"schema_version": "1.0", "task": task}), encoding="utf-8")
    package_root = project / "production"
    package = {
        "package_id": source_id,
        "shot_id": "SHT-TEST",
        "schema_version": "1.0",
        "source_fingerprint": "source-fingerprint",
        "package_fingerprint": "package-fingerprint",
        "provenance": {
            "integrated_package_id": "INT-TEST",
            "integrated_package_fingerprint": "integration-fingerprint",
            "planning_review_id": "REVIEW-TEST",
            "planning_review_fingerprint": "review-fingerprint",
        },
        "shot": {},
        "camera": {},
        "lighting": {},
        "environment": {},
    }
    package_path = package_root / "production_packages.json"
    package_path.write_text(
        json.dumps({"schema_version": "1.0", "production_packages": [package]}),
        encoding="utf-8",
    )
    return task_path, package_path


def _loader(project):
    service = object.__new__(ProductionPackageService)
    service.projects = SimpleNamespace(project_directory=project)
    service.planning = SimpleNamespace(
        current_package=lambda shot_id: SimpleNamespace(
            shot_id=shot_id, package_fingerprint="source-fingerprint"
        )
    )
    return H3PersistedAuthoritySource(
        tasks=JsonProductionTaskRepository(project / "production" / "scheduling" / "tasks"),
        packages=service,
        task_id="TASK-TEST",
        source_package_id="PKG-TEST",
        shot_id="SHT-TEST",
    )


def _verify(tmp_path):
    loader = _loader(tmp_path)
    return verify_persisted_h3_reference_authority(
        reference_root=tmp_path,
        tasks=loader.tasks,
        packages=loader.packages,
        original=SimpleNamespace(
            task_id="TASK-TEST",
            source_package_id="PKG-TEST",
            shot_id="SHT-TEST",
            profile="production",
        ),
        execution=SimpleNamespace(),
        projection=SimpleNamespace(),
    )


def test_real_persisted_sources_reach_real_compiler_and_reject_missing_approval_inputs(
    tmp_path,
):
    task_path, package_path = _write_records(tmp_path)
    before = (task_path.read_bytes(), package_path.read_bytes())
    with pytest.raises(
        H3ReferenceGovernanceError, match="cannot be independently recompiled"
    ) as error:
        _verify(tmp_path)
    assert "Universal Production Description authority is not compiled" in str(
        error.value.__cause__
    )
    assert (task_path.read_bytes(), package_path.read_bytes()) == before


def test_real_compiler_rejects_changed_task_authority_fingerprint(tmp_path):
    task_path, package_path = _write_records(tmp_path)
    raw = json.loads(package_path.read_text(encoding="utf-8"))
    package = raw["production_packages"][0]
    package["validation"] = {
        "universal_description_complete": True,
        "cross_authority_consistent": True,
    }
    package["universal_description"] = {"production": {"universal_text": "Test shot"}}
    package_path.write_text(json.dumps(raw), encoding="utf-8")
    before = (task_path.read_bytes(), package_path.read_bytes())
    with pytest.raises(
        H3ReferenceGovernanceError, match="cannot be independently recompiled"
    ) as error:
        _verify(tmp_path)
    assert "authority fingerprint does not match" in str(error.value.__cause__)
    assert (task_path.read_bytes(), package_path.read_bytes()) == before


def test_persisted_source_replacement_blocks_before_real_recompilation(tmp_path):
    task_path, package_path = _write_records(tmp_path)
    raw = json.loads(package_path.read_text(encoding="utf-8"))
    raw["production_packages"][0]["package_id"] = "REPLACED"
    package_path.write_text(json.dumps(raw), encoding="utf-8")
    before = (task_path.read_bytes(), package_path.read_bytes())
    with pytest.raises(H3ReferenceGovernanceError, match="exactly one"):
        _verify(tmp_path)
    assert (task_path.read_bytes(), package_path.read_bytes()) == before
