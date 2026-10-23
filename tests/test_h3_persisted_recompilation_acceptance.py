"""Q3.1.3.5.3 persisted-source to real compiler fail-closed acceptance.

Every filesystem is an isolated pytest tmp_path. No provider or production output runs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilerService,
)
from vscs.application.production_execution.span_scoped_provider_inputs import (
    SpanScopedProviderInputCompiler,
)
from vscs.application.production_package import ProductionPackageService
from vscs.application.provider_reference_capacity import ProviderReferenceCapacityProjection
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository
from vscs.infrastructure.production_execution.h3_persisted_authority_gate import (
    H3PersistedAuthoritySource,
    verify_persisted_h3_reference_authority,
)
from vscs.infrastructure.production_execution.h3_span_freshness_provenance import (
    validate_h3_span_freshness,
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


def test_valid_persisted_task_and_package_recompile_without_writes(tmp_path):
    """Positive path through real task and package readers plus real package compiler."""
    task_path, package_path = _write_records(tmp_path)
    document = json.loads(package_path.read_text(encoding="utf-8"))
    package = document["production_packages"][0]
    description = {
        "production": {
            "universal_text": "A controlled cinematic test shot.",
            "shot": {
                "production_objective": "Show a stationary engineering console.",
                "required_action": "The camera holds on the console.",
            },
            "action_performance": {"temporal_narrative": "The camera holds on the console."},
        }
    }
    package["universal_description"] = description
    package["validation"] = {
        "universal_description_complete": True,
        "cross_authority_consistent": True,
    }
    package_path.write_text(json.dumps(document), encoding="utf-8")
    task_document = json.loads(task_path.read_text(encoding="utf-8"))
    task_document["task"]["authority"]["fingerprint"] = hashlib.sha256(
        json.dumps(description, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    task_path.write_text(json.dumps(task_document), encoding="utf-8")
    before = (task_path.read_bytes(), package_path.read_bytes())

    task, source = _loader(tmp_path).load_current()
    compiler = ProductionPackageCompilerService(reference_root=tmp_path)
    compiled = compiler.compile(task, source, profile="production")

    assert compiled.task_id == task.task_id
    assert compiled.source_package_id == source.package_id
    assert compiled.source_package_fingerprint == source.package_fingerprint
    assert compiled.positive_prompt
    assert compiled.package_fingerprint
    assert compiler.compile(task, source, profile="production").package_fingerprint == (
        compiled.package_fingerprint
    )
    assert (task_path.read_bytes(), package_path.read_bytes()) == before


def test_positive_span_inputs_and_h3_freshness_with_isolated_temporal_contract(
    tmp_path, monkeypatch
):
    """Exercise actual span-input/freshness algorithms using a controlled temporal contract.

    Full persisted governed temporal authority remains a separate acceptance prerequisite.
    """
    task_path, package_path = _write_records(tmp_path)
    raw = json.loads(package_path.read_text(encoding="utf-8"))
    description = {
        "production": {
            "universal_text": "A cinematic view of the test bridge.",
            "shot": {"required_action": "Camera holds on the test bridge."},
        }
    }
    raw["production_packages"][0]["universal_description"] = description
    raw["production_packages"][0]["validation"] = {
        "universal_description_complete": True,
        "cross_authority_consistent": True,
    }
    package_path.write_text(json.dumps(raw), encoding="utf-8")
    task_doc = json.loads(task_path.read_text(encoding="utf-8"))
    task_doc["task"]["authority"]["fingerprint"] = hashlib.sha256(
        json.dumps(description, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    task_path.write_text(json.dumps(task_doc), encoding="utf-8")
    before = (task_path.read_bytes(), package_path.read_bytes())
    task, source = _loader(tmp_path).load_current()
    compiled = ProductionPackageCompilerService(reference_root=tmp_path).compile(
        task, source, profile="production"
    )
    reference = {
        "reference_id": "bridge-ref",
        "asset_id": "BRIDGE",
        "role": "environment_reference",
        "priority": "required",
        "provider_ready": True,
        "source_path": "references/bridge.png",
        "label": "Test Bridge",
    }
    compiled = replace(
        compiled,
        reference_plan={"status": "passed", "references": [reference]},
        composition_plan={
            **compiled.composition_plan,
            "assets": [{"asset_id": "BRIDGE", "name": "Test Bridge"}],
        },
    )
    temporal = SimpleNamespace(
        span_id="SPAN-1",
        sequence_number=1,
        active_asset_ids=("BRIDGE",),
        active_reference_ids=("bridge-ref",),
        future_reference_ids=(),
        execution_id="EXEC-1",
    )
    class TemporalCompiler:
        def compile(self, package):
            assert package is compiled
            return SimpleNamespace(fingerprint="temporal-fingerprint", executions=(temporal,))

    monkeypatch.setattr(
        "vscs.application.production_execution.span_scoped_provider_inputs."
        "ProviderTemporalSpanExecutionCompiler",
        TemporalCompiler,
    )
    plan = SpanScopedProviderInputCompiler().compile(compiled)
    assert plan.spans[0].reference_slots[0].reference_id == "bridge-ref"
    assert plan.spans[0].reference_slots[0].picture_tag == "<Picture 1>"
    execution = SimpleNamespace(
        span_id=plan.spans[0].span_id,
        sequence_number=plan.spans[0].sequence_number,
        source_span_input_plan_fingerprint=plan.fingerprint,
        reference_slots=plan.spans[0].reference_slots,
        deferred_reference_ids=(),
    )
    projection = ProviderReferenceCapacityProjection(
        provider_id="minimax-h3-ref2va",
        provider_profile_id="H3",
        provider_profile_fingerprint="isolated-test-policy",
        model_family="h3",
        reference_projection_mode="direct_span_scoped_canonical_refs",
        capacity=1,
        required_reference_ids=("bridge-ref",),
        preferred_ready_reference_ids=(),
        selected_reference_ids=("bridge-ref",),
        deferred_preferred_reference_ids=(),
        indirect_projection=False,
    )
    report = validate_h3_span_freshness(
        compiled, compiled, plan, execution, projection
    )
    assert report.advisory_only
    assert report.provider_profile_fingerprint == "isolated-test-policy"
    assert report.span_input_plan_fingerprint == plan.fingerprint
    assert (task_path.read_bytes(), package_path.read_bytes()) == before
