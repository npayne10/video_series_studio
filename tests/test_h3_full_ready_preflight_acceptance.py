"""Q3.1.3.5.6 full H3 READY preflight on temporary, never-production data.

All compilations are real; the only execution boundary is an explicit trap.
No VSCS TSR2 projects, ComfyUI server, generation or human QC are accessed.
"""

from __future__ import annotations

from dataclasses import replace
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
from vscs.infrastructure.production_execution.minimax_h3_automated_execution import (
    MiniMaxH3AutomatedExecutionService,
)
from vscs.infrastructure.production_execution.minimax_h3_comfyui_provider import (
    MiniMaxH3ComfyUIWorkflowCompiler,
)
from vscs.infrastructure.production_execution.minimax_h3_span_adapter import (
    MiniMaxH3SpanAdapterCompiler,
)
from vscs.infrastructure.production_execution.provider_policy_profiles import (
    MINIMAX_H3_POLICY_PROFILE_ID,
    default_provider_policy_profile_registry,
)


def test_full_real_h3_preflight_does_not_submit_or_mutate_governed_sources(tmp_path: Path):
    task_path, package_path = _governed_positive_fixture(tmp_path)
    reference_path = tmp_path / "references" / "bridge.png"
    before = tuple(path.read_bytes() for path in (task_path, package_path, reference_path))
    loader = _loader(tmp_path)
    task, source = loader.load_current()

    compiled = ProductionPackageCompilerService(reference_root=tmp_path).compile(
        task, source, profile="production"
    )
    # First-span guide is test-owned and content-addressed; never borrow media
    # from the user's existing project. Persisted source remains unchanged.
    compiled = replace(compiled, previous_approved_final_frame=str(reference_path))
    input_directory = tmp_path / "isolated_comfyui_input"
    input_directory.mkdir()
    workflow_path = (
        Path(__file__).resolve().parents[1]
        / "resources"
        / "workflows"
        / "manual"
        / "minimax_h3_ref2va_sht002_baseline_api.json"
    )
    assert workflow_path.is_file(), "The committed H3 API workflow fixture must exist"

    service = object.__new__(MiniMaxH3AutomatedExecutionService)
    service.project_directory = tmp_path
    service.task_repository = loader.tasks
    service.authority_packages = loader.packages
    service.execution_profile = "production"
    service.policy_profile = default_provider_policy_profile_registry().require(
        MINIMAX_H3_POLICY_PROFILE_ID
    )
    service.package_compiler = SimpleNamespace(
        compile_current=lambda current_task, profile: compiled
    )
    service.plan_compiler = MiniMaxH3SpanAdapterCompiler(tmp_path)
    service.workflow_compiler = MiniMaxH3ComfyUIWorkflowCompiler(
        tmp_path,
        comfyui_input_directory=input_directory,
        workflow_path=workflow_path,
    )
    service.orchestrator = SimpleNamespace(
        run=lambda *args, **kwargs: pytest.fail("Provider execution is forbidden in preflight")
    )

    result = service.preflight(task.task_id)
    assert result.task_id == task.task_id
    assert result.shot_id == task.shot_id
    assert result.span_count >= 1
    assert result.provider_profile_fingerprint == service.policy_profile.fingerprint
    assert len(result.workflow_fingerprints) == result.span_count
    assert all(result.workflow_fingerprints)
    assert tuple(path.read_bytes() for path in (task_path, package_path, reference_path)) == before
    assert not (tmp_path / "renders").exists()
    assert all(path.is_file() for path in input_directory.iterdir())
