"""Q3.1.3.5.1b: two REAL disk repositories, isolated under pytest tmp_path."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from vscs.application.production_package import ProductionPackageService
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository
from vscs.infrastructure.production_execution.h3_persisted_authority_gate import (
    H3PersistedAuthoritySource,
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
    return H3PersistedAuthoritySource(
        tasks=JsonProductionTaskRepository(project / "production" / "scheduling" / "tasks"),
        packages=service,
        task_id="TASK-TEST",
        source_package_id="PKG-TEST",
        shot_id="SHT-TEST",
    )


def test_both_real_disk_repositories_read_only(tmp_path):
    task_path, package_path = _write_records(tmp_path)
    before = (task_path.read_bytes(), package_path.read_bytes())
    task, source = _loader(tmp_path).load_current()
    assert task.task_id == "TASK-TEST"
    assert task.authority.approved
    assert source.package_id == "PKG-TEST"
    assert (task_path.read_bytes(), package_path.read_bytes()) == before


def test_task_changed_on_disk_fails_closed(tmp_path):
    task_path, _ = _write_records(tmp_path)
    first = _loader(tmp_path).load_current()
    assert first[0].shot_id == "SHT-TEST"
    document = json.loads(task_path.read_text(encoding="utf-8"))
    document["task"]["shot_id"] = "SHT-NEW"
    task_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(H3ReferenceGovernanceError, match="ProductionTask identity"):
        _loader(tmp_path).load_current()


def test_package_replaced_on_disk_fails_closed(tmp_path):
    _, package_path = _write_records(tmp_path)
    data = json.loads(package_path.read_text(encoding="utf-8"))
    data["production_packages"][0]["package_id"] = "PKG-REPLACED"
    package_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(H3ReferenceGovernanceError, match="exactly one"):
        _loader(tmp_path).load_current()


def test_missing_task_document_fails_closed(tmp_path):
    task_path, _ = _write_records(tmp_path)
    task_path.unlink()
    with pytest.raises(H3ReferenceGovernanceError, match="ProductionTask is missing"):
        _loader(tmp_path).load_current()
