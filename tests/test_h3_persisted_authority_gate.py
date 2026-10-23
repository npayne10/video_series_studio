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

    def current_package(self, shot_id):
        self.reads.append(f"current:{shot_id}")
        return next((item for item in reversed(self.records) if item.shot_id == shot_id), None)

    def persist(self, source):
        raise AssertionError("Source persistence must not be written")


def _source():
    task = SimpleNamespace(task_id="TASK-1", shot_id="SHOT-1")
    package = SimpleNamespace(package_id="PACKAGE-1", shot_id="SHOT-1", source_fingerprint="SRC", package_fingerprint="PKG")
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
    assert packages.reads == ["SHOT-1", "current:SHOT-1"]


def test_missing_task_blocks():
    tasks, packages = _source()
    tasks.records.clear()
    with pytest.raises(H3ReferenceGovernanceError, match="ProductionTask is missing"):
        _loader(tasks, packages).load_current()


def test_ambiguous_package_blocks():
    tasks, packages = _source()
    packages.records.append(SimpleNamespace(package_id="PACKAGE-1", shot_id="SHOT-1", source_fingerprint="SRC", package_fingerprint="PKG"))
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

    def fake_gate(
        *, reference_root, load_current_source, original, execution, projection, guide_overlap_ids
    ):
        task, package = load_current_source()
        called.append((task.task_id, package.package_id, reference_root))
        return "read-only-verified"

    monkeypatch.setattr(gate, "verify_current_h3_reference_authority", fake_gate)
    assert (
        gate.verify_persisted_h3_reference_authority(
            reference_root=tmp_path,
            tasks=tasks,
            packages=packages,
            original=original,
            execution=SimpleNamespace(),
            projection=SimpleNamespace(),
        )
        == "read-only-verified"
    )
    assert called == [("TASK-1", "PACKAGE-1", tmp_path)]


def test_superseded_package_fails_closed():
    tasks, packages = _source()
    packages.records.append(
        SimpleNamespace(
            package_id="PACKAGE-NEW",
            shot_id="SHOT-1",
            source_fingerprint="SRC",
            package_fingerprint="NEW",
        )
    )
    with pytest.raises(H3ReferenceGovernanceError, match="not the current"):
        _loader(tasks, packages).load_current()


def test_missing_current_planning_authority_fails_closed():
    tasks, packages = _source()
    packages.current_package = lambda shot_id: None
    with pytest.raises(H3ReferenceGovernanceError, match="authority is missing"):
        _loader(tasks, packages).load_current()


def test_current_package_lookup_failure_fails_closed():
    tasks, packages = _source()

    def broken_lookup(shot_id):
        raise RuntimeError("Planning authority cannot be read")

    packages.current_package = broken_lookup
    with pytest.raises(H3ReferenceGovernanceError, match="Unable to verify"):
        _loader(tasks, packages).load_current()


def test_changed_package_fingerprint_fails_closed():
    tasks, packages = _source()
    current = SimpleNamespace(
        package_id="PACKAGE-1",
        shot_id="SHOT-1",
        source_fingerprint="SRC",
        package_fingerprint="CHANGED",
    )
    packages.current_package = lambda shot_id: current
    with pytest.raises(H3ReferenceGovernanceError, match="not the current"):
        _loader(tasks, packages).load_current()


def test_changed_source_fingerprint_fails_closed():
    tasks, packages = _source()
    current = SimpleNamespace(
        package_id="PACKAGE-1",
        shot_id="SHOT-1",
        source_fingerprint="CHANGED",
        package_fingerprint="PKG",
    )
    packages.current_package = lambda shot_id: current
    with pytest.raises(H3ReferenceGovernanceError, match="not the current"):
        _loader(tasks, packages).load_current()
