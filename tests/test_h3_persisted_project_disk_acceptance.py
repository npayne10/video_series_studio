"""Q3.1.3.5.1 disk-backed package authority acceptance in an isolated tmp_path.

Never opens or mutates the operator's production project.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from vscs.application.production_package import ProductionPackageService
from vscs.infrastructure.production_execution.h3_persisted_authority_gate import (
    H3PersistedAuthoritySource,
)
from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceGovernanceError,
)


class ReadOnlyTaskRepository:
    def __init__(self) -> None:
        self.task = SimpleNamespace(task_id="TASK-TEST", shot_id="SHT-TEST")

    def get(self, task_id: str) -> SimpleNamespace | None:
        return self.task if task_id == self.task.task_id else None

    def save(self, task: object) -> None:
        raise AssertionError("Task writes forbidden")


def _isolated_package_service(tmp_path):
    service = object.__new__(ProductionPackageService)
    service.projects = SimpleNamespace(project_directory=tmp_path)
    service.planning = SimpleNamespace(
        current_package=lambda shot_id: SimpleNamespace(
            shot_id=shot_id, package_fingerprint="governed-source"
        )
    )
    # ProductionPackageService.list_packages reads the actual project JSON via
    # its canonical serializer; no production database or planner is opened.
    return service


def _record(package_id: str = "PKG-TEST") -> dict[str, object]:
    return {
        "package_id": package_id,
        "shot_id": "SHT-TEST",
        "schema_version": "1.0",
        "source_fingerprint": "governed-source",
        "package_fingerprint": "compiled-source",
        "provenance": {
            "integrated_package_id": "INT-TEST",
            "integrated_package_fingerprint": "integration-sha",
            "planning_review_id": "REVIEW-TEST",
            "planning_review_fingerprint": "review-sha",
        },
        "shot": {},
        "camera": {},
        "lighting": {},
        "environment": {},
    }


def _write_project(tmp_path, records):
    path = tmp_path / "production" / "production_packages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": "1.0", "production_packages": records}),
        encoding="utf-8",
    )
    return path


def _loader(tmp_path):
    return H3PersistedAuthoritySource(
        tasks=ReadOnlyTaskRepository(),
        packages=_isolated_package_service(tmp_path),
        task_id="TASK-TEST",
        source_package_id="PKG-TEST",
        shot_id="SHT-TEST",
    )


def test_real_production_package_json_read_is_repeatable(tmp_path):
    path = _write_project(tmp_path, [_record()])
    original_bytes = path.read_bytes()
    task, package = _loader(tmp_path).load_current()
    assert task.task_id == "TASK-TEST"
    assert package.package_id == "PKG-TEST"
    assert package.source_fingerprint == "governed-source"
    assert _loader(tmp_path).load_current()[1].package_fingerprint == "compiled-source"
    assert path.read_bytes() == original_bytes


def test_missing_persisted_package_fails_closed(tmp_path):
    _write_project(tmp_path, [])
    with pytest.raises(H3ReferenceGovernanceError, match="exactly one"):
        _loader(tmp_path).load_current()


def test_ambiguous_persisted_package_fails_closed(tmp_path):
    _write_project(tmp_path, [_record(), _record()])
    with pytest.raises(H3ReferenceGovernanceError, match="exactly one"):
        _loader(tmp_path).load_current()


def test_changed_persisted_package_identity_fails_closed(tmp_path):
    path = _write_project(tmp_path, [_record()])
    path.write_text(
        json.dumps({"schema_version": "1.0", "production_packages": [_record("PKG-NEW")]}),
        encoding="utf-8",
    )
    with pytest.raises(H3ReferenceGovernanceError, match="exactly one"):
        _loader(tmp_path).load_current()
