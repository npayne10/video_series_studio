from pathlib import Path

from PySide6.QtCore import Qt

from vscs.application.production_execution import (
    ProductionDeviceTelemetry,
    ProductionExecutionCandidate,
    ProductionExecutionResult,
    ProductionExecutionState,
    ProductionExecutionUiService,
    ProductionPackageCompilationState,
    ProductionPackageStatus,
    ProductionTelemetrySnapshot,
    ProductionTelemetryState,
    ProviderExecutionReadiness,
    ProviderExecutionReadinessState,
)
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType
from vscs.infrastructure.production_execution import (
    MINIMAX_H3_POLICY_PROFILE_ID,
    default_provider_policy_profile_registry,
)
from vscs.presentation.widgets.production_execution_workspace import ProductionExecutionWorkspace


class WorkspaceBackend:
    def __init__(self, package_path: Path, *, execution_exists: bool = False) -> None:
        self.package_path = package_path
        self.package_path.parent.mkdir(parents=True, exist_ok=True)
        self.candidate = ProductionExecutionCandidate(
            production_id="XORIX",
            task_id="PT-20-15-UI-001",
            task_type=ProductionTaskType.VIDEO_GENERATION,
            task_state=ProductionTaskState.READY,
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
            resource_id="GPU-01",
            queue_entry_id="PQE-PT-20-15-UI-001",
            label="Video Generation — SHT-001",
        )
        self.compiled = False
        self.execution_exists = execution_exists
        self.completed = False
        self.start_calls = 0
        self.reconcile_calls = 0

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        return (self.candidate,)

    def has_execution(self, task_id: str) -> bool:
        assert task_id == self.candidate.task_id
        return self.execution_exists

    def telemetry(self, task_id: str) -> ProductionTelemetrySnapshot:
        assert task_id == self.candidate.task_id
        assert self.execution_exists
        if self.completed:
            return ProductionTelemetrySnapshot(
                task_id=task_id,
                state=ProductionTelemetryState.COMPLETED,
                live=False,
                execution_id="PEX-20-15-UI-001",
                provider_id="LOCAL-COMFYUI-GPU-01",
                provider_job_id="prompt-20-15-ui",
                resource_id="GPU-01",
                queue_entry_id="PQE-PT-20-15-UI-001",
                stage="Durable execution summary",
                progress=1.0,
                elapsed_seconds=45.0,
                queue_state="durable-summary",
                message="Completed durable summary",
            )
        live = self.start_calls > 0
        return ProductionTelemetrySnapshot(
            task_id=task_id,
            state=ProductionTelemetryState.RUNNING,
            live=live,
            execution_id="PEX-20-15-UI-001",
            provider_id="LOCAL-COMFYUI-GPU-01",
            provider_job_id="prompt-20-15-ui",
            resource_id="GPU-01",
            queue_entry_id="PQE-PT-20-15-UI-001",
            stage=("Generating video in ComfyUI" if live else "Durable execution summary"),
            progress=0.5,
            elapsed_seconds=20.0,
            queue_state="running" if live else "durable-summary",
            queue_running_count=1 if live else 0,
            provider_healthy=True if live else None,
            devices=(
                ProductionDeviceTelemetry(
                    name="NVIDIA RTX 4060",
                    kind="cuda",
                    total_memory_bytes=8 * 1024**3,
                    free_memory_bytes=2 * 1024**3,
                ),
            )
            if live
            else (),
            message="Live HTTP telemetry active" if live else "Durable execution summary only",
        )

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        assert task_id == self.candidate.task_id
        return ProductionPackageStatus(
            task_id=task_id,
            state=(
                ProductionPackageCompilationState.COMPILED
                if self.compiled
                else ProductionPackageCompilationState.NOT_COMPILED
            ),
            profile=profile,
            path=self.package_path,
            authority_fingerprint="authority",
            package_fingerprint="package" if self.compiled else None,
            message="Compiled" if self.compiled else "Not compiled",
        )

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        assert task_id == self.candidate.task_id
        self.compiled = True
        self.package_path.write_text("{}", encoding="utf-8")
        return self.package_status(task_id, profile=profile)

    def start(
        self,
        task_id: str,
        *,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        assert task_id == self.candidate.task_id
        assert production_package is None
        assert self.compiled
        self.start_calls += 1
        self.execution_exists = True
        return ProductionExecutionResult(
            candidate=self.candidate,
            state=ProductionExecutionState.SUBMITTED,
            provider_id="LOCAL-COMFYUI-GPU-01",
            execution_id="PEX-20-15-UI-001",
            provider_job_id="prompt-20-15-ui",
            progress=0.0,
            media_output_directory="Media Output",
            message="Provider submitted",
        )

    def reconcile(self, task_id: str) -> ProductionExecutionResult:
        assert task_id == self.candidate.task_id
        assert self.execution_exists
        self.reconcile_calls += 1
        self.completed = True
        return ProductionExecutionResult(
            candidate=self.candidate,
            state=ProductionExecutionState.COMPLETED,
            provider_id="LOCAL-COMFYUI-GPU-01",
            execution_id="PEX-20-15-UI-001",
            provider_job_id="prompt-20-15-ui",
            progress=1.0,
            generated_media_ids=("GM-20-15-UI-001",),
            media_output_directory="Media Output",
            message="Provider completed; outputs ingested as authoritative Generated Media.",
        )


def _compiled_workspace(
    qtbot, tmp_path: Path
) -> tuple[WorkspaceBackend, ProductionExecutionWorkspace]:
    backend = WorkspaceBackend(tmp_path / "production_package.json")
    service = ProductionExecutionUiService(backend)
    workspace = ProductionExecutionWorkspace(lambda: service)
    qtbot.addWidget(workspace)
    workspace.refresh()
    workspace.table.selectRow(0)
    qtbot.mouseClick(workspace.compile_package_button, Qt.MouseButton.LeftButton)
    return backend, workspace


def test_workspace_compiles_package_before_starting_scheduled_work(qtbot, tmp_path: Path) -> None:
    backend = WorkspaceBackend(tmp_path / "production_package.json")
    service = ProductionExecutionUiService(backend)
    workspace = ProductionExecutionWorkspace(lambda: service)
    qtbot.addWidget(workspace)

    workspace.refresh()
    assert workspace.table.rowCount() == 1
    assert not workspace.start_button.isEnabled()

    workspace.table.selectRow(0)
    assert workspace.compile_package_button.isEnabled()
    assert not workspace.start_button.isEnabled()
    assert not workspace.status_button.isEnabled()
    assert "NOT_COMPILED" in workspace.package_state.text()

    qtbot.mouseClick(workspace.compile_package_button, Qt.MouseButton.LeftButton)
    assert workspace.start_button.isEnabled()
    assert not workspace.status_button.isEnabled()
    assert "COMPILED" in workspace.package_state.text()

    qtbot.mouseClick(workspace.start_button, Qt.MouseButton.LeftButton)
    assert backend.start_calls == 1
    assert not workspace.start_button.isEnabled()
    assert workspace.status_button.isEnabled()
    assert workspace._poll_timer.isActive()
    assert "SUBMITTED" in workspace.summary.text()
    assert workspace.overall_progress.value() == 50
    assert "RUNNING" in workspace.monitor_state.text()
    assert workspace.monitor_health.text() == "Healthy"
    assert "RTX 4060" in workspace.monitor_device.text()

    qtbot.mouseClick(workspace.status_button, Qt.MouseButton.LeftButton)
    assert backend.reconcile_calls == 1
    assert not workspace.status_button.isEnabled()
    assert not workspace._poll_timer.isActive()
    assert not workspace.start_button.isEnabled()
    assert "COMPLETED" in workspace.summary.text()
    assert workspace.overall_progress.value() == 100
    assert "GM-20-15-UI-001" in workspace.details.toPlainText()
    assert "Project Media Output: Media Output" in workspace.details.toPlainText()


def test_workspace_automatic_poll_reconciles_active_execution(qtbot, tmp_path: Path) -> None:
    backend, workspace = _compiled_workspace(qtbot, tmp_path)
    qtbot.mouseClick(workspace.start_button, Qt.MouseButton.LeftButton)

    workspace._poll_live_status()

    assert backend.reconcile_calls == 1
    assert not workspace._poll_timer.isActive()
    assert "COMPLETED" in workspace.monitor_state.text()


def test_workspace_enables_status_for_existing_durable_execution(qtbot, tmp_path: Path) -> None:
    backend = WorkspaceBackend(
        tmp_path / "production_package.json",
        execution_exists=True,
    )
    service = ProductionExecutionUiService(backend)
    workspace = ProductionExecutionWorkspace(lambda: service)
    qtbot.addWidget(workspace)

    workspace.refresh()
    workspace.table.selectRow(0)

    assert workspace.status_button.isEnabled()
    assert not workspace._poll_timer.isActive()
    assert "DURABLE SUMMARY" in workspace.monitor_state.text()
    assert workspace.monitor_health.text() == "Not live"


class ProviderSelectionWorkspaceBackend(WorkspaceBackend):
    def __init__(self, package_path: Path) -> None:
        super().__init__(package_path)
        self.registry = default_provider_policy_profile_registry()
        self.selected_provider_profile_id = "ltx-2.5-candidate-c-v1"

    def provider_policy_profiles(self):
        return self.registry.enabled_profiles

    def provider_policy_profile_for_profile(self, task_id: str, *, profile: str):
        assert task_id == self.candidate.task_id
        assert profile in {"preview", "production", "master"}
        return self.registry.require(self.selected_provider_profile_id)

    def select_provider_policy_profile_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        provider_profile_id: str,
    ):
        assert task_id == self.candidate.task_id
        assert profile in {"preview", "production", "master"}
        selected = self.registry.require(provider_profile_id)
        self.selected_provider_profile_id = selected.profile_id
        return selected

    def provider_execution_readiness_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> ProviderExecutionReadiness:
        selected = self.registry.require(self.selected_provider_profile_id)
        return ProviderExecutionReadiness(
            task_id=task_id,
            shot_id=self.candidate.shot_id or "SHT-001",
            execution_profile=profile,
            provider_profile_id=selected.profile_id,
            provider_profile_fingerprint=selected.fingerprint,
            execution_adapter_id=selected.execution_adapter_id,
            package_fingerprint="package-fingerprint",
            timed_span_state="outputs_required",
            span_count=2,
            requirement_count=1,
            approved_keyframe_count=1,
            state=ProviderExecutionReadinessState.READY,
            provider_plan_id="PLAN-READY",
            provider_plan_fingerprint="a" * 64,
        )


def test_workspace_selects_governed_span_provider_profile(qtbot, tmp_path: Path) -> None:
    backend = ProviderSelectionWorkspaceBackend(tmp_path / "production_package.json")
    service = ProductionExecutionUiService(backend)
    workspace = ProductionExecutionWorkspace(lambda: service)
    qtbot.addWidget(workspace)

    workspace.refresh()
    workspace.table.selectRow(0)

    assert workspace.provider_policy.isEnabled()
    assert workspace.provider_policy.count() == 2
    assert workspace.provider_policy.currentData() == "ltx-2.5-candidate-c-v1"

    h3_index = workspace.provider_policy.findData(MINIMAX_H3_POLICY_PROFILE_ID)
    assert h3_index >= 0
    workspace.provider_policy.setCurrentIndex(h3_index)

    assert backend.selected_provider_profile_id == MINIMAX_H3_POLICY_PROFILE_ID
    assert "MiniMax H3" in workspace.summary.text()
    assert workspace.validate_provider_readiness_button.isEnabled()

    qtbot.mouseClick(
        workspace.validate_provider_readiness_button,
        Qt.MouseButton.LeftButton,
    )

    assert "READY" in workspace.provider_readiness_state.text()
    assert "PLAN-READY" in workspace.provider_readiness_state.text()
