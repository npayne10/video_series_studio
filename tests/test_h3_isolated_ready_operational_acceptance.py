"""Non-destructive READY H3 readiness acceptance on a wholly isolated project.

Real JSON task/package readers, package compiler, temporal reference compiler and
persisted H3 authority/freshness gate. The H3 provider-specific span adapter and
workflow compiler are deliberately controlled stand-ins: no ComfyUI, QC or media.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_h3_persisted_recompilation_acceptance import (
    _governed_positive_fixture,
    _loader,
)
from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilerService,
)
from vscs.application.production_execution.span_scoped_provider_inputs import (
    SpanScopedProviderInputCompiler,
)
from vscs.infrastructure.production_execution.minimax_h3_automated_execution import (
    MiniMaxH3AutomatedExecutionError,
    MiniMaxH3AutomatedExecutionService,
)
from vscs.infrastructure.production_execution.provider_policy_profiles import (
    MINIMAX_H3_POLICY_PROFILE_ID,
    default_provider_policy_profile_registry,
)


def _ready_service(tmp_path: Path):
    task_path, package_path = _governed_positive_fixture(tmp_path)
    image_path = tmp_path / "references" / "bridge.png"
    loader = _loader(tmp_path)
    task, source = loader.load_current()
    compiled = ProductionPackageCompilerService(reference_root=tmp_path).compile(
        task, source, profile="production"
    )
    span_inputs = SpanScopedProviderInputCompiler().compile(compiled)
    policy = default_provider_policy_profile_registry().require(MINIMAX_H3_POLICY_PROFILE_ID)
    execution = SimpleNamespace(
        span_id=span_inputs.spans[0].span_id,
        sequence_number=span_inputs.spans[0].sequence_number,
        source_span_input_plan_fingerprint=span_inputs.fingerprint,
        reference_slots=span_inputs.spans[0].reference_slots,
        deferred_reference_ids=(),
        provider_id=policy.provider_id,
        job_id="ISOLATED-READY-SPAN",
        prompt_fingerprint="isolated-prompt",
        reference_slot_fingerprint="isolated-refs",
        prompt_validation_fingerprint="isolated-prompt-validation",
    )
    plan = SimpleNamespace(
        spans=(execution,),
        provider_id=policy.provider_id,
        provider_profile_id=policy.profile_id,
        provider_profile_fingerprint=policy.fingerprint,
        execution_adapter_id=policy.execution_adapter_id,
        plan_id="ISOLATED-READY-PLAN",
        fingerprint="isolated-ready-plan-fingerprint",
    )
    service = object.__new__(MiniMaxH3AutomatedExecutionService)
    service.project_directory = tmp_path
    service.task_repository = loader.tasks
    service.authority_packages = loader.packages
    service.policy_profile = policy
    service.execution_profile = "production"
    service.package_compiler = SimpleNamespace(
        compile_current=lambda current_task, profile: compiled
    )
    service.plan_compiler = SimpleNamespace(compile=lambda package: plan)
    workflow_calls: list[str] = []

    def compile_workflow(span):
        workflow_calls.append(span.span_id)
        return SimpleNamespace(
            workflow_fingerprint="isolated-workflow",
            model_config_fingerprint="isolated-model",
        )

    service.workflow_compiler = SimpleNamespace(compile=compile_workflow)
    service.orchestrator = SimpleNamespace(
        run=lambda *args, **kwargs: pytest.fail("No H3 provider or orchestration may run")
    )
    sources = (task_path, package_path, image_path)
    return service, compiled, workflow_calls, sources


def test_ready_preflight_verifies_real_persisted_freshness_without_writes(tmp_path: Path):
    service, compiled, calls, sources = _ready_service(tmp_path)
    before = tuple(path.read_bytes() for path in sources)
    result = service.preflight(compiled.task_id)
    assert result.task_id == compiled.task_id
    assert result.span_count == 1
    assert result.package_fingerprint == compiled.package_fingerprint
    assert calls == [service.plan_compiler.compile(compiled).spans[0].span_id]
    assert tuple(path.read_bytes() for path in sources) == before
    assert not (tmp_path / "renders").exists()


def test_stale_ready_fixture_blocks_workflow_without_rewriting_records(tmp_path: Path):
    service, compiled, calls, sources = _ready_service(tmp_path)
    source = sources[1]
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["production_packages"][0]["package_id"] = "REPLACED"
    source.write_text(json.dumps(payload), encoding="utf-8")
    before = tuple(path.read_bytes() for path in sources)
    with pytest.raises(MiniMaxH3AutomatedExecutionError, match="freshness authority is blocked"):
        service.preflight(compiled.task_id)
    assert calls == []
    assert tuple(path.read_bytes() for path in sources) == before


def test_controlled_h3_dry_run_is_read_only_and_never_submits(tmp_path: Path):
    service, compiled, calls, sources = _ready_service(tmp_path)
    before = tuple(path.read_bytes() for path in sources)
    report = service.dry_run(compiled.task_id)
    assert report.task_id == compiled.task_id
    assert report.span_count == 1
    assert calls
    assert tuple(path.read_bytes() for path in sources) == before
    assert not (tmp_path / "renders").exists()
