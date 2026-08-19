from pathlib import Path

from PySide6.QtCore import Qt

from vscs.application.production_execution import (
    ProductionExecutionCandidate,
    ProductionExecutionResult,
    ProductionExecutionState,
    ProductionExecutionUiService,
)
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType
from vscs.presentation.widgets.production_execution_workspace import ProductionExecutionWorkspace


class WorkspaceBackend:
    def __init__(self) -> None:
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
        self.start_calls = 0
        self.reconcile_calls = 0

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        return (self.candidate,)

    def start(self, task_id: str, *, production_package: Path) -> ProductionExecutionResult:
        assert task_id == self.candidate.task_id
        assert production_package.is_file()
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


def test_workspace_starts_and_monitors_selected_scheduled_work(qtbot, tmp_path: Path) -> None:
    backend = WorkspaceBackend()
    service = ProductionExecutionUiService(backend)
    workspace = ProductionExecutionWorkspace(lambda: service)
    qtbot.addWidget(workspace)

    workspace.refresh()
    assert workspace.table.rowCount() == 1
    assert not workspace.start_button.isEnabled()

    workspace.table.selectRow(0)
    package = tmp_path / "production-package.json"
    package.write_text("{}", encoding="utf-8")
    workspace.production_package.setText(str(package))

    assert workspace.start_button.isEnabled()
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
