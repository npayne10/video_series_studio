from pathlib import Path

import pytest

from vscs.application.production_execution import (
    ProductionExecutionCandidate,
    ProductionExecutionError,
    ProductionExecutionResult,
    ProductionExecutionState,
    ProductionExecutionUiService,
    ProductionPackageCompilationState,
    ProductionPackageStatus,
)
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType


class RecordingBackend:
    def __init__(self, *, execution_exists: bool = False) -> None:
        self.candidate = ProductionExecutionCandidate(
            production_id="XORIX",
            task_id="PT-20-15-001",
            task_type=ProductionTaskType.VIDEO_GENERATION,
            task_state=ProductionTaskState.READY,
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
            resource_id="GPU-01",
            queue_entry_id="PQE-PT-20-15-001",
            label="Video Generation — SHT-001",
        )
        self.execution_exists = execution_exists
        self.started: tuple[str, Path] | None = None
        self.reconciled: str | None = None

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        return (self.candidate,)

    def has_execution(self, task_id: str) -> bool:
        assert task_id == self.candidate.task_id
        return self.execution_exists

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        assert task_id == self.candidate.task_id
        return ProductionPackageStatus(
            task_id=task_id,
            state=ProductionPackageCompilationState.COMPILED,
            profile=profile,
            path=Path("production-package.json"),
            message="compiled",
        )

    def start(
        self,
        task_id: str,
        *,
        production_package: Path,
    ) -> ProductionExecutionResult:
        self.started = (task_id, production_package)
        return ProductionExecutionResult(
            candidate=self.candidate,
            state=ProductionExecutionState.SUBMITTED,
            provider_id="LOCAL-COMFYUI-GPU-01",
        )

    def reconcile(self, task_id: str) -> ProductionExecutionResult:
        self.reconciled = task_id
        return ProductionExecutionResult(
            candidate=self.candidate,
            state=ProductionExecutionState.RUNNING,
            provider_id="LOCAL-COMFYUI-GPU-01",
            progress=0.5,
        )


def test_ui_service_delegates_scheduled_candidate_discovery() -> None:
    backend = RecordingBackend()
    service = ProductionExecutionUiService(backend)

    assert service.candidates() == (backend.candidate,)


def test_ui_service_requires_existing_json_production_package(tmp_path: Path) -> None:
    service = ProductionExecutionUiService(RecordingBackend())

    with pytest.raises(ProductionExecutionError, match="does not exist"):
        service.start("PT-20-15-001", tmp_path / "missing.json")

    text_file = tmp_path / "package.txt"
    text_file.write_text("{}", encoding="utf-8")
    with pytest.raises(ProductionExecutionError, match="must be a JSON file"):
        service.start("PT-20-15-001", text_file)


def test_ui_service_passes_resolved_package_to_backend(tmp_path: Path) -> None:
    backend = RecordingBackend()
    service = ProductionExecutionUiService(backend)
    package = tmp_path / "package.json"
    package.write_text("{}", encoding="utf-8")

    result = service.start("PT-20-15-001", package)

    assert result.state is ProductionExecutionState.SUBMITTED
    assert backend.started == ("PT-20-15-001", package.resolve())


def test_ui_service_blocks_duplicate_execution_start(tmp_path: Path) -> None:
    backend = RecordingBackend(execution_exists=True)
    service = ProductionExecutionUiService(backend)
    package = tmp_path / "package.json"
    package.write_text("{}", encoding="utf-8")

    with pytest.raises(ProductionExecutionError, match="preflight is execution-exists"):
        service.start("PT-20-15-001", package)

    assert backend.started is None


def test_ui_service_reconcile_requires_selected_task() -> None:
    service = ProductionExecutionUiService(RecordingBackend())

    with pytest.raises(ProductionExecutionError, match="Select a ProductionTask"):
        service.reconcile("   ")
