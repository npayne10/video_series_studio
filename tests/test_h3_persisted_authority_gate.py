"""Q3.1.3.5 isolated repository-read authority acceptance tests."""

from types import SimpleNamespace

import pytest

from vscs.infrastructure.production_execution import h3_persisted_authority_gate as gate
from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceGovernanceError,
)


class ReadOnlyTasks:
    def __init__(self, records):
        self.records = records
        self.reads = []

    def get(self, task_id):
        self.reads.append(task_id)
        return self.records.get(task_id)

    def save(self, task):
        raise AssertionError("Task persistence must not be written")


class ReadOnlyPackages:
    def __init__(self, records):
        self.records = records
        self.reads = []

    def list_packages(self, *, shot_id=None):
        self.reads.append(shot_id)
        return tuple(item for item in self.records if item.shot_id == shot_id)

    def persist(self, source):
        raise AssertionError("Source persistence must not be written")


def _source():
    task = SimpleNamespace(task_id="TASK-1", shot_id="SHOT-1")
    package = SimpleNamespace(package_id="PACKAGE-1", shot_id="SHOT-1")
    return ReadOnlyTasks({"TASK-1": task}), ReadOnlyPackages([package])


def _loader(tasks, packages):
    return gate.H3PersistedAuthoritySource(
        tasks=tasks,
        packages=packages,
        task_id="TASK-1",
        source_package_id="PACKAGE-1",
        shot_id="SHOT-1",
    )


def test_exact_persisted_authority_read():
    tasks, packages = _source()
    task, source = _loader(tasks, packages).load_current()
    assert task.task_id == "TASK-1"
    assert source.package_id == "PACKAGE-1"
    assert tasks.reads == ["TASK-1"]
    assert packages.reads == ["SHOT-1"]


def test_missing_task_blocks():
    tasks, packages = _source()
    tasks.records.clear()
    with pytest.raises(H3ReferenceGovernanceError, match="ProductionTask is missing"):
        _loader(tasks, packages).load_current()


def test_ambiguous_package_blocks():
    tasks, packages = _source()
    packages.records.append(SimpleNamespace(package_id="PACKAGE-1", shot_id="SHOT-1"))
    with pytest.raises(H3ReferenceGovernanceError, match="exactly one"):
        _loader(tasks, packages).load_current()


def test_wrong_shot_task_blocks():
    tasks, packages = _source()
    tasks.records["TASK-1"].shot_id = "OTHER"
    with pytest.raises(H3ReferenceGovernanceError, match="identity"):
        _loader(tasks, packages).load_current()


def test_wrapper_passes_repository_loader_to_freshness_gate(monkeypatch, tmp_path):
    tasks, packages = _source()
    original = SimpleNamespace(task_id="TASK-1", source_package_id="PACKAGE-1", shot_id="SHOT-1")
    called = []

    def fake_gate(*, reference_root, load_current_source, original, execution, projection, guide_overlap_ids):
        task, package = load_current_source()
        called.append((task.task_id, package.package_id, reference_root))
        return "read-only-verified"

    monkeypatch.setattr(gate, "verify_current_h3_reference_authority", fake_gate)
    assert gate.verify_persisted_h3_reference_authority(
        reference_root=tmp_path,
        tasks=tasks,
        packages=packages,
        original=original,
        execution=SimpleNamespace(),
        projection=SimpleNamespace(),
    ) == "read-only-verified"
    assert called == [("TASK-1", "PACKAGE-1", tmp_path)]
