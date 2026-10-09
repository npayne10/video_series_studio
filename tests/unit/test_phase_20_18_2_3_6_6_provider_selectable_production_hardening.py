from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest

import vscs.infrastructure.production_execution.ltx25_keyframe_backend as backend_module
from vscs.application.production_execution import (
    ProductionExecutionError,
    ProviderExecutionReadiness,
    ProviderExecutionReadinessState,
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
)
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.infrastructure.production_execution import (
    MINIMAX_H3_POLICY_PROFILE_ID,
    LocalComfyUIProductionExecutionBackend,
    ProviderProductionAdoptionStore,
)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-FIRST-REAL-SHOT-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-002",
        shot_id="EP-001-SCN-002-SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-FIRST-REAL-SHOT",
            revision=1,
            fingerprint="authority-fingerprint",
            approved=True,
            approved_by="Neill Payne",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
        created_at=datetime(2026, 10, 9, 11, 0, tzinfo=UTC),
    )


class _PackageCompilation:
    def __init__(self, package_path: Path) -> None:
        self.package_path = package_path

    def status(self, task: ProductionTask, *, profile: str = "production"):
        assert task.task_id == "PT-FIRST-REAL-SHOT-001"
        return SimpleNamespace(
            executable=True,
            path=self.package_path,
            package_fingerprint="package-fingerprint",
            message="",
        )

    def compile_current(self, task: ProductionTask, *, profile: str = "production"):
        assert task.task_id == "PT-FIRST-REAL-SHOT-001"
        return SimpleNamespace(package_fingerprint="package-fingerprint")

    def require_current(self, task: ProductionTask, *, profile: str = "production"):
        return self.status(task, profile=profile)


class _H3Execution:
    executed: ClassVar[bool] = False

    def __init__(self, project_directory: Path, **kwargs) -> None:
        assert kwargs["execution_profile"] == "production"
        assert kwargs["policy_profile"].profile_id == MINIMAX_H3_POLICY_PROFILE_ID

    def preflight(self, task_id: str):
        assert task_id == "PT-FIRST-REAL-SHOT-001"
        return SimpleNamespace(
            plan_id="H3SPANPLAN-FIRST-REAL-SHOT",
            plan_fingerprint="a" * 64,
        )

    def execute(self, task_id: str):
        assert task_id == "PT-FIRST-REAL-SHOT-001"
        type(self).executed = True
        return SimpleNamespace(final_path="assembled.mp4")


class _Acceptance:
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    @staticmethod
    def _status(state: TimedSpanAcceptanceState) -> TimedSpanAcceptanceStatus:
        if state is TimedSpanAcceptanceState.OUTPUTS_REQUIRED:
            return TimedSpanAcceptanceStatus(
                shot_id="EP-001-SCN-002-SHT-001",
                state=state,
                span_count=2,
                boundary_count=1,
                requirement_count=1,
                approved_keyframe_count=1,
                qc_passed_count=0,
                assembly_present=False,
                message="Normalized span outputs must be verified and assembled.",
                requirement_ids=("REQ-001",),
                pending_qc_requirement_ids=("REQ-001",),
            )
        if state is TimedSpanAcceptanceState.QC_REQUIRED:
            return TimedSpanAcceptanceStatus(
                shot_id="EP-001-SCN-002-SHT-001",
                state=state,
                span_count=2,
                boundary_count=1,
                requirement_count=1,
                approved_keyframe_count=1,
                qc_passed_count=0,
                assembly_present=True,
                final_frame_count=144,
                message="1 visual introduction-boundary QC approval remains.",
                final_path="Media Output/first-real-shot.mp4",
                requirement_ids=("REQ-001",),
                pending_qc_requirement_ids=("REQ-001",),
            )
        return TimedSpanAcceptanceStatus(
            shot_id="EP-001-SCN-002-SHT-001",
            state=TimedSpanAcceptanceState.ACCEPTED,
            span_count=2,
            boundary_count=1,
            requirement_count=1,
            approved_keyframe_count=1,
            qc_passed_count=1,
            assembly_present=True,
            final_frame_count=144,
            message="Timed-span functional acceptance passed.",
            final_path="Media Output/first-real-shot.mp4",
            requirement_ids=("REQ-001",),
        )

    def status(
        self,
        package_path: Path,
        *,
        direct_approved_keyframes: bool = False,
    ) -> TimedSpanAcceptanceStatus:
        assert direct_approved_keyframes is True
        state = (
            TimedSpanAcceptanceState.QC_REQUIRED
            if _H3Execution.executed
            else TimedSpanAcceptanceState.OUTPUTS_REQUIRED
        )
        return self._status(state)

    def record_visual_qc(
        self,
        package_path: Path,
        *,
        direct_approved_keyframes: bool = False,
        **kwargs,
    ) -> TimedSpanAcceptanceStatus:
        assert direct_approved_keyframes is True
        assert kwargs["approved_by"] == "Neill Payne"
        return self._status(TimedSpanAcceptanceState.ACCEPTED)





class _BlockedAcceptance(_Acceptance):
    def status(
        self,
        package_path: Path,
        *,
        direct_approved_keyframes: bool = False,
    ) -> TimedSpanAcceptanceStatus:
        assert direct_approved_keyframes is True
        return TimedSpanAcceptanceStatus(
            shot_id="EP-001-SCN-002-SHT-001",
            state=TimedSpanAcceptanceState.KEYFRAME_REQUIRED,
            span_count=2,
            boundary_count=1,
            requirement_count=1,
            approved_keyframe_count=0,
            qc_passed_count=0,
            assembly_present=False,
            message="1 governed Introduction Keyframe approval remains.",
            requirement_ids=("REQ-001",),
            pending_keyframe_requirement_ids=("REQ-001",),
            pending_qc_requirement_ids=("REQ-001",),
        )


def _backend(tmp_path: Path, monkeypatch):
    project = tmp_path / "project"
    output_dir = tmp_path / "ComfyUI" / "output"
    input_dir = tmp_path / "ComfyUI" / "input"
    project.mkdir()
    output_dir.mkdir(parents=True)
    input_dir.mkdir(parents=True)
    package_path = project / "production-package.json"
    package_path.write_text("{}", encoding="utf-8")

    backend = LocalComfyUIProductionExecutionBackend(
        project,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=output_dir,
    )
    task = _task()
    backend.tasks.save(task)
    backend.package_compilation = _PackageCompilation(package_path)  # type: ignore[assignment]
    backend.provider_policy_selections.select(
        task.task_id,
        "production",
        MINIMAX_H3_POLICY_PROFILE_ID,
    )
    _H3Execution.executed = False
    monkeypatch.setattr(
        backend_module,
        "MiniMaxH3AutomatedExecutionService",
        _H3Execution,
    )
    monkeypatch.setattr(
        backend_module,
        "TimedSpanFunctionalAcceptanceService",
        _Acceptance,
    )
    return backend, task


def test_provider_readiness_contract_is_deterministic() -> None:
    readiness = ProviderExecutionReadiness(
        task_id="PT-001",
        shot_id="SHT-001",
        execution_profile="production",
        provider_profile_id="minimax-h3-ref2va-v1",
        provider_profile_fingerprint="a" * 64,
        execution_adapter_id="minimax_h3_automated_execution",
        package_fingerprint="b" * 64,
        timed_span_state="outputs_required",
        span_count=2,
        requirement_count=1,
        approved_keyframe_count=1,
        state=ProviderExecutionReadinessState.READY,
        provider_plan_id="PLAN-001",
        provider_plan_fingerprint="c" * 64,
    )

    assert readiness.ready_to_execute
    assert readiness.readiness_id.startswith("PER-")
    assert len(readiness.fingerprint) == 64
    assert readiness.to_dict()["fingerprint"] == readiness.fingerprint


def test_h3_normal_production_preflight_is_ready_and_persisted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend, task = _backend(tmp_path, monkeypatch)

    readiness = backend.provider_execution_readiness_for_profile(
        task.task_id,
        profile="production",
    )

    assert readiness.state is ProviderExecutionReadinessState.READY
    assert readiness.ready_to_execute
    assert readiness.provider_profile_id == MINIMAX_H3_POLICY_PROFILE_ID
    assert readiness.provider_plan_id == "H3SPANPLAN-FIRST-REAL-SHOT"
    readiness_path = (
        backend.project_directory
        / ".vscs"
        / "production_execution"
        / "provider_execution_readiness.json"
    )
    assert readiness_path.is_file()


def test_h3_normal_production_records_generated_and_accepted_adoption(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend, task = _backend(tmp_path, monkeypatch)

    generated = backend.run_automated_timed_span_orchestration_for_profile(
        task.task_id,
        profile="production",
    )

    assert generated.state is TimedSpanAcceptanceState.QC_REQUIRED
    store = ProviderProductionAdoptionStore(backend.project_directory)
    adoption = store.adoption_for(task.task_id, "production")
    assert adoption is not None
    assert adoption.state == "generated_pending_visual_qc"
    assert adoption.final_frame_count == 144
    assert adoption.provider_profile_id == MINIMAX_H3_POLICY_PROFILE_ID

    accepted = backend.record_timed_span_qc_for_profile(
        task.task_id,
        profile="production",
        requirement_id="REQ-001",
        absent_before_boundary=True,
        present_from_target_frame=True,
        source_continuity_preserved=True,
        no_unapproved_assets=True,
        approved_by="Neill Payne",
        notes="First provider-selectable real-shot adoption accepted.",
    )

    assert accepted.state is TimedSpanAcceptanceState.ACCEPTED
    adoption = store.adoption_for(task.task_id, "production")
    assert adoption is not None
    assert adoption.state == "accepted"
    assert adoption.approved_by == "Neill Payne"



def test_provider_execution_rechecks_readiness_and_blocks_missing_keyframe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend, task = _backend(tmp_path, monkeypatch)
    monkeypatch.setattr(
        backend_module,
        "TimedSpanFunctionalAcceptanceService",
        _BlockedAcceptance,
    )

    readiness = backend.provider_execution_readiness_for_profile(
        task.task_id,
        profile="production",
    )
    assert readiness.state is ProviderExecutionReadinessState.BLOCKED
    assert not readiness.ready_to_execute
    assert "Introduction Keyframe" in readiness.blockers[0]

    with pytest.raises(
        ProductionExecutionError,
        match="not ready to execute",
    ):
        backend.run_automated_timed_span_orchestration_for_profile(
            task.task_id,
            profile="production",
        )

    assert _H3Execution.executed is False
