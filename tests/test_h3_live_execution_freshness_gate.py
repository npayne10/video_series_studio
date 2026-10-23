"""Q3.1.3.5.4: H3 live preflight must enforce persisted freshness before execution.

No network, ComfyUI, or production filesystem access is permitted in these tests.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.application.production_package import ProductionPackageService
from vscs.infrastructure.production_execution import minimax_h3_automated_execution as h3
from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceGovernanceError,
)


def _harness(*, packages=None):
    calls = []

    class PlanCompiler:
        def compile(self, compiled):
            calls.append("plan")
            return SimpleNamespace(
                spans=(
                    SimpleNamespace(
                        span_id="S-1",
                        reference_slots=(SimpleNamespace(reference_id="REF-1"),),
                        deferred_reference_ids=(),
                    ),
                ),
            )

    class WorkflowCompiler:
        def compile(self, execution):
            calls.append("workflow")
            raise AssertionError("Provider workflow must not compile before freshness validation")

    service = object.__new__(h3.MiniMaxH3AutomatedExecutionService)
    service.plan_compiler = PlanCompiler()
    service.workflow_compiler = WorkflowCompiler()
    service.authority_packages = packages
    service.policy_profile = SimpleNamespace(
        provider_id="minimax-h3-ref2va",
        profile_id="minimax-h3-ref2va-v1",
        execution_adapter_id="minimax_h3_automated_execution",
        fingerprint="policy-sha",
        model_family="MiniMax H3",
        reference_projection_mode="direct_span_scoped_canonical_refs",
        max_reference_images=5,
    )
    service.project_directory = None
    service.execution_profile = "production"
    service.task_repository = SimpleNamespace()
    compiled = SimpleNamespace(
        task_id="TASK-1",
        shot_id="SHOT-1",
        package_fingerprint="PACKAGE-1",
        reference_plan={
            "status": "passed",
            "references": [
                {
                    "reference_id": "REF-1",
                    "role": "environment_reference",
                    "priority": "required",
                    "provider_ready": True,
                }
            ],
        },
    )
    return service, compiled, calls


def test_unwired_real_planning_authority_blocks_before_provider_workflow():
    service, compiled, calls = _harness()
    with pytest.raises(
        h3.MiniMaxH3AutomatedExecutionError,
        match="authenticated current planning/package authority",
    ):
        service._preflight_compiled(compiled)
    assert calls == ["plan"]


def test_stale_persisted_authority_blocks_before_provider_workflow(monkeypatch):
    service, compiled, calls = _harness(packages=SimpleNamespace())
    verified = []

    def reject(**kwargs):
        verified.append(kwargs)
        raise H3ReferenceGovernanceError("Current ProductionPackage authority is missing")

    monkeypatch.setattr(h3, "verify_persisted_h3_reference_authority", reject)
    with pytest.raises(h3.MiniMaxH3AutomatedExecutionError, match="freshness authority is blocked"):
        service._preflight_compiled(compiled)
    assert len(verified) == 1
    assert verified[0]["packages"] is service.authority_packages
    assert verified[0]["tasks"] is service.task_repository
    assert calls == ["plan"]


def test_validated_preflight_allows_provider_payload_only_after_freshness(monkeypatch):
    service, compiled, calls = _harness(packages=SimpleNamespace())
    span = SimpleNamespace(
        span_id="S-1",
        sequence_number=1,
        provider_id="minimax-h3-ref2va",
        job_id="JOB-1",
        prompt_fingerprint="PROMPT-1",
        reference_slot_fingerprint="SLOTS-1",
        prompt_validation_fingerprint="VALID-1",
        reference_slots=(SimpleNamespace(reference_id="REF-1"),),
        deferred_reference_ids=(),
    )
    policy = service.policy_profile
    service.plan_compiler.compile = lambda value: SimpleNamespace(
        spans=(span,),
        provider_id=policy.provider_id,
        provider_profile_id=policy.profile_id,
        provider_profile_fingerprint=policy.fingerprint,
        execution_adapter_id="minimax_h3_automated_execution",
        plan_id="PLAN-1",
        fingerprint="PLAN-FP-1",
    )

    def verify(**kwargs):
        calls.append("freshness")
        assert kwargs["packages"] is service.authority_packages
        assert kwargs["original"] is compiled
        assert kwargs["execution"] is span
        return SimpleNamespace(verified_against_current_loader=True)

    def workflow(execution):
        calls.append("workflow")
        assert execution is span
        return SimpleNamespace(
            workflow_fingerprint="WORKFLOW-1",
            model_config_fingerprint="MODEL-1",
        )

    monkeypatch.setattr(h3, "verify_persisted_h3_reference_authority", verify)
    service.workflow_compiler.compile = workflow
    result = service._preflight_compiled(compiled)
    assert result.span_count == 1
    assert result.package_fingerprint == "PACKAGE-1"
    assert calls == ["freshness", "workflow"]


def test_live_execute_does_not_submit_when_authority_is_unwired():
    service, compiled, calls = _harness()
    service.task_repository = SimpleNamespace(get=lambda task_id: SimpleNamespace(task_id=task_id))
    service.package_compiler = SimpleNamespace(compile_current=lambda task, profile: compiled)
    service.orchestrator = SimpleNamespace(
        run=lambda *args, **kwargs: pytest.fail("Provider submission must not occur")
    )
    with pytest.raises(
        h3.MiniMaxH3AutomatedExecutionError,
        match="authenticated current planning/package authority",
    ):
        service.execute("TASK-1")
    assert calls == ["plan"]


def test_real_project_factory_wires_current_planning_backed_package_service(
    tmp_path: Path, monkeypatch
):
    """The production factory must pass the actual ProductionPackageService."""
    project = SimpleNamespace(project_directory=tmp_path)
    integrated = SimpleNamespace(
        shot_id="SHT-FACTORY",
        package_fingerprint="source-fingerprint",
    )
    planning = SimpleNamespace(
        projects=project,
        current_package=lambda shot_id: integrated,
    )
    source = {
        "package_id": "PKG-FACTORY",
        "shot_id": "SHT-FACTORY",
        "schema_version": "1.0",
        "source_fingerprint": "source-fingerprint",
        "package_fingerprint": "package-fingerprint",
        "provenance": {
            "integrated_package_id": "INT-FACTORY",
            "integrated_package_fingerprint": "integration-fingerprint",
            "planning_review_id": "REVIEW-FACTORY",
            "planning_review_fingerprint": "review-fingerprint",
        },
        "shot": {},
        "camera": {},
        "lighting": {},
        "environment": {},
    }
    import json

    root = tmp_path / "production"
    root.mkdir()
    (root / "production_packages.json").write_text(
        json.dumps({"schema_version": "1.0", "production_packages": [source]}),
        encoding="utf-8",
    )
    forwarded = {}

    def capture_init(self, project_directory, **kwargs):
        forwarded.update(project_directory=project_directory, **kwargs)

    monkeypatch.setattr(h3.MiniMaxH3AutomatedExecutionService, "__init__", capture_init)
    h3.MiniMaxH3AutomatedExecutionService.from_project_services(
        project,
        planning,
        endpoint="http://127.0.0.1:8188",
        comfyui_input_directory=tmp_path,
        comfyui_output_directory=tmp_path,
    )
    assert forwarded["project_directory"] == tmp_path
    packages = forwarded["authority_packages"]
    assert isinstance(packages, ProductionPackageService)
    assert packages.projects is project
    assert packages.planning is planning
    current = packages.current_package("SHT-FACTORY")
    assert current is not None
    assert current.package_id == "PKG-FACTORY"


def test_project_factory_fails_closed_on_cross_project_planning(
    tmp_path: Path, monkeypatch
):
    project = SimpleNamespace(project_directory=tmp_path)
    planning = SimpleNamespace(projects=SimpleNamespace(project_directory=tmp_path))
    monkeypatch.setattr(
        h3.MiniMaxH3AutomatedExecutionService,
        "__init__",
        lambda self, *args, **kwargs: pytest.fail("No service may be constructed"),
    )
    with pytest.raises(
        h3.MiniMaxH3AutomatedExecutionError,
        match="does not belong to the open VSCS project",
    ):
        h3.MiniMaxH3AutomatedExecutionService.from_project_services(
            project,
            planning,
            endpoint="http://127.0.0.1:8188",
            comfyui_input_directory=tmp_path,
            comfyui_output_directory=tmp_path,
        )
