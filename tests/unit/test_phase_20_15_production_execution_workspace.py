from pathlib import Path

from PySide6.QtCore import Qt

from vscs.application.production_execution import (
    ProductionExecutionCandidate,
    ProductionExecutionResult,
    ProductionExecutionState,
    ProductionExecutionUiService,
    ProductionPackageCompilationState,
    ProductionPackageStatus,
)
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType
from vscs.presentation.widgets.production_execution_workspace import ProductionExecutionWorkspace


class WorkspaceBackend:
    def __init__(self, package_path: Path) -> None:
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
        self.start_calls = 0
        self.reconcile_calls = 0

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        return (self.candidate,)

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
        self.reconcile_calls += 1
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
    assert "NOT_COMPILED" in workspace.package_state.text()

    qtbot.mouseClick(workspace.compile_package_button, Qt.MouseButton.LeftButton)
    assert workspace.start_button.isEnabled()
    assert "COMPILED" in workspace.package_state.text()

    qtbot.mouseClick(workspace.start_button, Qt.MouseButton.LeftButton)
    assert backend.start_calls == 1
    assert not workspace.start_button.isEnabled()
    assert workspace.status_button.isEnabled()
    assert "SUBMITTED" in workspace.summary.text()

    qtbot.mouseClick(workspace.status_button, Qt.MouseButton.LeftButton)
    assert backend.reconcile_calls == 1
    assert not workspace.status_button.isEnabled()
    assert workspace.start_button.isEnabled()
    assert "COMPLETED" in workspace.summary.text()
    assert "GM-20-15-UI-001" in workspace.details.toPlainText()
    assert "Project Media Output: Media Output" in workspace.details.toPlainText()
