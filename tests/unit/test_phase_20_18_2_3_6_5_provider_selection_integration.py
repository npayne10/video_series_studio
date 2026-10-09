from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import vscs.infrastructure.production_execution.ltx25_keyframe_backend as backend_module
from vscs.application.production_execution import (
    ProductionExecutionUiService,
    TimedSpanAcceptanceState,
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
    LTX25_CANDIDATE_C_POLICY_PROFILE_ID,
    MINIMAX_H3_POLICY_PROFILE_ID,
    LocalComfyUIProductionExecutionBackend,
    ProviderPolicySelectionStore,
    default_provider_policy_profile_registry,
)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-PROVIDER-SELECTION-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-002",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SHT-002",
            revision=1,
            fingerprint="authority",
            approved=True,
            approved_by="Neill Payne",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
        created_at=datetime(2026, 10, 7, 12, 0, tzinfo=UTC),
    )


def test_provider_policy_selection_store_defaults_to_ltx_and_persists_per_profile(
    tmp_path: Path,
) -> None:
    store = ProviderPolicySelectionStore(tmp_path)

    default = store.selected_profile("PT-001", "production")
    assert default.profile_id == LTX25_CANDIDATE_C_POLICY_PROFILE_ID

    selected = store.select("PT-001", "production", MINIMAX_H3_POLICY_PROFILE_ID)
    assert selected.profile_id == MINIMAX_H3_POLICY_PROFILE_ID

    reloaded = ProviderPolicySelectionStore(tmp_path)
    assert (
        reloaded.selected_profile("PT-001", "production").profile_id == MINIMAX_H3_POLICY_PROFILE_ID
    )
    assert (
        reloaded.selected_profile("PT-001", "preview").profile_id
        == LTX25_CANDIDATE_C_POLICY_PROFILE_ID
    )


class _SelectionBackend:
    def __init__(self, project: Path) -> None:
        self.store = ProviderPolicySelectionStore(project)
        self.registry = default_provider_policy_profile_registry()

    def provider_policy_profiles(self):
        return self.registry.enabled_profiles

    def provider_policy_profile_for_profile(self, task_id: str, *, profile: str):
        return self.store.selected_profile(task_id, profile)

    def select_provider_policy_profile_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        provider_profile_id: str,
    ):
        return self.store.select(task_id, profile, provider_profile_id)


def test_execution_ui_service_selects_governed_provider_profile(tmp_path: Path) -> None:
    service = ProductionExecutionUiService(_SelectionBackend(tmp_path))  # type: ignore[arg-type]

    profiles = service.provider_policy_profiles()
    assert {item.profile_id for item in profiles} == {
        LTX25_CANDIDATE_C_POLICY_PROFILE_ID,
        MINIMAX_H3_POLICY_PROFILE_ID,
    }

    selected = service.select_provider_policy_profile(
        "PT-001",
        MINIMAX_H3_POLICY_PROFILE_ID,
        profile="production",
    )
    assert selected.profile_id == MINIMAX_H3_POLICY_PROFILE_ID
    assert (
        service.provider_policy_profile("PT-001", profile="production").fingerprint
        == selected.fingerprint
    )


class _PackageCompilation:
    def __init__(self, package_path: Path) -> None:
        self.package_path = package_path

    def status(self, task: ProductionTask, *, profile: str = "production"):
        assert task.task_id == "PT-PROVIDER-SELECTION-001"
        assert profile == "production"
        return SimpleNamespace(
            executable=True,
            path=self.package_path,
            package_fingerprint="package-fingerprint",
            message="",
        )

    def compile_current(self, task: ProductionTask, *, profile: str = "production"):
        assert task.task_id == "PT-PROVIDER-SELECTION-001"
        assert profile == "production"
        return SimpleNamespace(package_fingerprint="package-fingerprint")

    def require_current(self, task: ProductionTask, *, profile: str = "production"):
        assert task.task_id == "PT-PROVIDER-SELECTION-001"
        assert profile == "production"
        return SimpleNamespace(path=self.package_path)


class _H3Execution:
    calls: ClassVar[list[tuple[str, str]]] = []

    def __init__(self, project_directory: Path, **kwargs) -> None:
        assert kwargs["execution_profile"] == "production"
        assert kwargs["policy_profile"].profile_id == MINIMAX_H3_POLICY_PROFILE_ID
        assert Path(kwargs["comfyui_input_directory"]).name == "input"
        assert Path(kwargs["comfyui_output_directory"]).name == "output"

    def preflight(self, task_id: str):
        assert task_id == "PT-PROVIDER-SELECTION-001"
        return SimpleNamespace(
            plan_id="H3SPANPLAN-PROVIDER-SELECTION",
            plan_fingerprint="a" * 64,
        )

    def execute(self, task_id: str):
        self.calls.append((task_id, "execute"))
        return SimpleNamespace(final_path="assembled.mp4")


class _Acceptance:
    calls: ClassVar[list[bool]] = []

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    def status(
        self,
        package_path: Path,
        *,
        direct_approved_keyframes: bool = False,
    ):
        self.calls.append(direct_approved_keyframes)
        generated = bool(_H3Execution.calls)
        return SimpleNamespace(
            marker="h3-normal-flow",
            package_path=package_path,
            direct_approved_keyframes=direct_approved_keyframes,
            applicable=True,
            pending_keyframe_requirement_ids=(),
            accepted=False,
            assembly_present=generated,
            state=(
                TimedSpanAcceptanceState.QC_REQUIRED
                if generated
                else TimedSpanAcceptanceState.OUTPUTS_REQUIRED
            ),
            span_count=2,
            requirement_count=1,
            approved_keyframe_count=1,
            final_path=(
                "Media Output/provider-selection-h3.mp4"
                if generated
                else None
            ),
            final_frame_count=144 if generated else None,
        )


def test_normal_backend_routes_selected_h3_profile_without_acceptance_harness(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    comfyui = tmp_path / "ComfyUI"
    input_dir = comfyui / "input"
    output_dir = comfyui / "output"
    project.mkdir()
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
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

    _H3Execution.calls.clear()
    _Acceptance.calls.clear()
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

    status = backend.run_automated_timed_span_orchestration_for_profile(
        task.task_id,
        profile="production",
    )

    assert status.marker == "h3-normal-flow"
    assert status.direct_approved_keyframes is True
    assert _H3Execution.calls == [(task.task_id, "execute")]
    assert _Acceptance.calls == [True, True]


def test_h3_selected_status_uses_direct_approved_keyframe_authority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    output_dir = tmp_path / "ComfyUI" / "output"
    project.mkdir()
    output_dir.mkdir(parents=True)
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

    _Acceptance.calls.clear()
    monkeypatch.setattr(
        backend_module,
        "TimedSpanFunctionalAcceptanceService",
        _Acceptance,
    )

    status = backend.timed_span_acceptance_status_for_profile(
        task.task_id,
        profile="production",
    )

    assert status.marker == "h3-normal-flow"
    assert status.direct_approved_keyframes is True
    assert _Acceptance.calls == [True]
