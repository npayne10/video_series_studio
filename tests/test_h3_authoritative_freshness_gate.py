"""Q3.1.3.4 independently loaded source freshness gates."""

from types import SimpleNamespace

import pytest

from vscs.infrastructure.production_execution import h3_authoritative_freshness_gate as gate
from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceGovernanceError,
)


def _setup(monkeypatch, tmp_path, *, current_fingerprint="same"):
    original = SimpleNamespace(shot_id="SHT-1", profile="production", package_fingerprint="same")
    task = SimpleNamespace(shot_id="SHT-1")
    source = SimpleNamespace(shot_id="SHT-1")
    refreshed = SimpleNamespace(package_fingerprint=current_fingerprint)
    plan = SimpleNamespace(fingerprint="span-plan")
    calls = []

    class FakeCompiler:
        def __init__(self, *, reference_root):
            assert reference_root == tmp_path

        def compile(self, actual_task, actual_source, *, profile):
            calls.append(("compile", actual_task, actual_source, profile))
            return refreshed

    class FakeSpanCompiler:
        def compile(self, actual):
            assert actual is refreshed
            calls.append(("span",))
            return plan

    def validate(a, b, sp, execution, projection, *, guide_overlap_ids):
        assert a is original and b is refreshed and sp is plan
        assert guide_overlap_ids == frozenset()
        calls.append(("validate",))
        if a.package_fingerprint != b.package_fingerprint:
            raise H3ReferenceGovernanceError("Compiled package source is stale")
        return SimpleNamespace(fingerprint="verified")

    monkeypatch.setattr(gate, "ProductionPackageCompilerService", FakeCompiler)
    monkeypatch.setattr(gate, "SpanScopedProviderInputCompiler", FakeSpanCompiler)
    monkeypatch.setattr(gate, "validate_h3_span_freshness", validate)
    return original, task, source, calls


def test_gate_recompiles_supplied_current_source(monkeypatch, tmp_path):
    original, task, source, calls = _setup(monkeypatch, tmp_path)
    result = gate.verify_current_h3_reference_authority(
        reference_root=tmp_path,
        load_current_source=lambda: (task, source),
        original=original,
        execution=SimpleNamespace(),
        projection=SimpleNamespace(),
    )
    assert result.report.fingerprint == "verified"
    assert result.advisory_only
    assert [item[0] for item in calls] == ["compile", "span", "validate"]


def test_changed_shot_fails_before_compile(monkeypatch, tmp_path):
    original, task, source, calls = _setup(monkeypatch, tmp_path)
    source.shot_id = "OTHER"
    with pytest.raises(H3ReferenceGovernanceError, match="Shot identity"):
        gate.verify_current_h3_reference_authority(
            reference_root=tmp_path,
            load_current_source=lambda: (task, source),
            original=original,
            execution=SimpleNamespace(),
            projection=SimpleNamespace(),
        )
    assert not calls


def test_stale_recompilation_fails_closed(monkeypatch, tmp_path):
    original, task, source, _ = _setup(monkeypatch, tmp_path, current_fingerprint="new")
    with pytest.raises(H3ReferenceGovernanceError, match="stale"):
        gate.verify_current_h3_reference_authority(
            reference_root=tmp_path,
            load_current_source=lambda: (task, source),
            original=original,
            execution=SimpleNamespace(),
            projection=SimpleNamespace(),
        )


def test_unavailable_source_fails_closed(monkeypatch, tmp_path):
    original, _, _, _ = _setup(monkeypatch, tmp_path)

    def unavailable():
        raise FileNotFoundError("missing")

    with pytest.raises(H3ReferenceGovernanceError, match="cannot be independently recompiled"):
        gate.verify_current_h3_reference_authority(
            reference_root=tmp_path,
            load_current_source=unavailable,
            original=original,
            execution=SimpleNamespace(),
            projection=SimpleNamespace(),
        )
