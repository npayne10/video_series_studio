from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from vscs.application.production_execution import CompiledProductionPackage
from vscs.application.production_tasks import ProductionTask
from vscs.infrastructure.production_execution import (
    MiniMaxH3AutomatedExecutionError,
    MiniMaxH3AutomatedExecutionService,
)


class _Tasks:
    def __init__(self, task: ProductionTask | None) -> None:
        self.task = task

    def get(self, task_id: str) -> ProductionTask | None:
        if self.task is not None and self.task.task_id == task_id:
            return self.task
        return None


class _Packages:
    def __init__(self, compiled: CompiledProductionPackage) -> None:
        self.compiled = compiled
        self.calls = 0

    def compile_current(self, task: ProductionTask) -> CompiledProductionPackage:
        self.calls += 1
        return self.compiled


class _Plans:
    def __init__(self, plan: object) -> None:
        self.plan = plan
        self.calls = 0

    def compile(self, compiled: CompiledProductionPackage):
        self.calls += 1
        return self.plan


class _Workflows:
    def __init__(self, jobs: tuple[object, ...], *, fail: bool = False) -> None:
        self.jobs = list(jobs)
        self.fail = fail
        self.calls = 0

    def compile(self, execution: object):
        self.calls += 1
        if self.fail:
            from vscs.infrastructure.production_execution.minimax_h3_comfyui_provider import (
                MiniMaxH3ComfyUIProviderError,
            )

            raise MiniMaxH3ComfyUIProviderError("invalid provider payload")
        return self.jobs.pop(0)


class _Orchestrator:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls = 0
        self.compiled = None

    def run(self, compiled: CompiledProductionPackage, *, output_path: Path | None = None):
        self.calls += 1
        self.compiled = compiled
        return self.result


def _task() -> ProductionTask:
    from datetime import UTC, datetime

    from vscs.application.production_tasks import (
        ProductionAuthorityType,
        ProductionCapability,
        ProductionTaskAuthority,
        ProductionTaskState,
        ProductionTaskType,
    )

    return ProductionTask(
        task_id="PT-VIDEO-001",
        production_id="PROD-001",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-002",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="SHT-002",
            revision=1,
            fingerprint="authority",
            approved=True,
            approved_by="Neill",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
        created_at=datetime(2026, 10, 7, tzinfo=UTC),
    )


def _compiled() -> CompiledProductionPackage:
    return cast(
        CompiledProductionPackage,
        SimpleNamespace(
            task_id="PT-VIDEO-001",
            shot_id="SHT-002",
            package_fingerprint="package-fingerprint",
        ),
    )


def _execution(sequence: int):
    return SimpleNamespace(
        job_id=f"H3SPAN-{sequence:03d}",
        prompt_fingerprint=f"prompt-{sequence}",
        reference_slot_fingerprint=f"refs-{sequence}",
    )


def _plan():
    return SimpleNamespace(
        plan_id="H3SPANPLAN-SHT-002",
        fingerprint="plan-fingerprint",
        spans=(_execution(1), _execution(2)),
    )


def _job(sequence: int):
    return SimpleNamespace(
        workflow_fingerprint=f"workflow-{sequence}",
        model_config_fingerprint=f"model-{sequence}",
    )


def _service(
    tmp_path: Path,
    *,
    workflow_fail: bool = False,
):
    input_dir = tmp_path / "ComfyUI" / "input"
    output_dir = tmp_path / "ComfyUI" / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    workflow = tmp_path / "workflow.json"
    workflow.write_text("{}", encoding="utf-8")

    compiled = _compiled()
    packages = _Packages(compiled)
    plans = _Plans(_plan())
    workflows = _Workflows((_job(1), _job(2)), fail=workflow_fail)
    result = cast(object, SimpleNamespace(task_id="PT-VIDEO-001", shot_id="SHT-002"))
    orchestrator = _Orchestrator(result)
    service = MiniMaxH3AutomatedExecutionService(
        tmp_path,
        endpoint="http://127.0.0.1:8188",
        comfyui_input_directory=input_dir,
        comfyui_output_directory=output_dir,
        workflow_path=workflow,
        task_repository=_Tasks(_task()),
        package_compiler=packages,
        plan_compiler=plans,
        workflow_compiler=workflows,
        orchestrator=orchestrator,
    )
    return service, packages, plans, workflows, orchestrator, result


def test_h3_automated_preflight_wires_all_governed_spans_to_provider_payloads(
    tmp_path: Path,
) -> None:
    service, packages, plans, workflows, orchestrator, _ = _service(tmp_path)

    result = service.preflight("PT-VIDEO-001")

    assert result.task_id == "PT-VIDEO-001"
    assert result.shot_id == "SHT-002"
    assert result.span_count == 2
    assert result.span_job_ids == ("H3SPAN-001", "H3SPAN-002")
    assert result.prompt_fingerprints == ("prompt-1", "prompt-2")
    assert result.reference_slot_fingerprints == ("refs-1", "refs-2")
    assert result.workflow_fingerprints == ("workflow-1", "workflow-2")
    assert result.model_config_fingerprints == ("model-1", "model-2")
    assert packages.calls == 1
    assert plans.calls == 1
    assert workflows.calls == 2
    assert orchestrator.calls == 0


def test_h3_automated_execute_preflights_before_orchestration(tmp_path: Path) -> None:
    service, packages, plans, workflows, orchestrator, expected = _service(tmp_path)

    result = service.execute("PT-VIDEO-001")

    assert result is expected
    assert packages.calls == 1
    assert plans.calls == 1
    assert workflows.calls == 2
    assert orchestrator.calls == 1
    assert orchestrator.compiled is packages.compiled


def test_h3_automated_execute_fails_before_provider_when_payload_preflight_fails(
    tmp_path: Path,
) -> None:
    service, _, _, workflows, orchestrator, _ = _service(
        tmp_path,
        workflow_fail=True,
    )

    with pytest.raises(
        MiniMaxH3AutomatedExecutionError,
        match="provider payload preflight failed",
    ):
        service.execute("PT-VIDEO-001")

    assert workflows.calls == 1
    assert orchestrator.calls == 0


def test_h3_automated_execution_requires_known_task(tmp_path: Path) -> None:
    service, _, _, _, _, _ = _service(tmp_path)
    service.task_repository = _Tasks(None)

    with pytest.raises(
        MiniMaxH3AutomatedExecutionError,
        match="cannot find ProductionTask",
    ):
        service.preflight("PT-UNKNOWN")
