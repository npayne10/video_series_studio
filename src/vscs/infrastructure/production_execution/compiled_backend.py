"""Phase 20.15.1 production-package-aware ComfyUI execution backend."""

from __future__ import annotations

from pathlib import Path

from vscs.application.production_execution import (
    ProductionExecutionError,
    ProductionExecutionResult,
    ProductionPackageStatus,
    ProductionTelemetrySnapshot,
)
from vscs.application.production_tasks import ProductionTask

from .comfyui_backend import (
    LocalComfyUIProductionExecutionBackend as _Phase2015ComfyUIBackend,
)
from .live_telemetry import ComfyUIProductionTelemetryReader
from .package_compilation import (
    ComfyUIV714InputAssurance,
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)


class LocalComfyUIProductionExecutionBackend(_Phase2015ComfyUIBackend):
    """Extend Phase 20.15 execution with governed package compilation and assurance."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_output_directory: Path | None,
        managed_media_directory: str = "Media Output",
        lease_duration_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            project_directory,
            endpoint=endpoint,
            comfyui_output_directory=comfyui_output_directory,
            managed_media_directory=managed_media_directory,
            lease_duration_seconds=lease_duration_seconds,
        )
        self.package_compilation = LocalProductionPackageCompilationService(self.project_directory)
        self.input_assurance = ComfyUIV714InputAssurance()

    def has_execution(self, task_id: str) -> bool:
        """Return whether an active or durable execution exists for the task."""
        task = self._require_task(task_id)
        if task.task_id in self._active:
            return True
        return bool(self.execution_jobs.list_for_task(task.task_id))

    def telemetry(self, task_id: str) -> ProductionTelemetrySnapshot:
        """Return current-session live telemetry or a durable non-live summary."""
        task = self._require_task(task_id)
        reader = ComfyUIProductionTelemetryReader(self.endpoint)
        active = self._active.get(task.task_id)
        if active is not None:
            return reader.observe_live(
                active.handle,
                task_id=task.task_id,
                resource_id=active.candidate.resource_id,
                queue_entry_id=active.candidate.queue_entry_id,
            )
        jobs = self.execution_jobs.list_for_task(task.task_id)
        if jobs:
            return reader.observe_durable(jobs[-1])
        raise ProductionExecutionError(f"No execution exists for ProductionTask: {task.task_id}")

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        task = self._require_task(task_id)
        return self.package_compilation.status(task, profile=profile)

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        task = self._require_task(task_id)
        workflow_path = (
            Path(__file__).resolve().parents[4]
            / "resources"
            / "workflows"
            / "workflows"
            / "video_production_engine_v7_1_4_api.json"
        )
        assurance = self.input_assurance.inspect(workflow_path)
        if not assurance.passed:
            raise ProductionExecutionError(
                "ComfyUI production workflow input assurance failed: " + "; ".join(assurance.issues)
            )
        try:
            return self.package_compilation.compile(task, profile=profile)
        except LocalProductionPackageCompilationError as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def start(
        self,
        task_id: str,
        *,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        task = self._require_task(task_id)
        if self.has_execution(task.task_id):
            raise ProductionExecutionError(
                "ProductionTask already has an execution record. Inspect or reconcile that "
                "execution; direct duplicate starts are not allowed."
            )
        try:
            if production_package is None:
                package = self.package_compilation.require_current(task).path
                assert package is not None
            else:
                package = Path(production_package).expanduser().resolve(strict=False)
                self.package_compilation.validate_file(task, package)
        except LocalProductionPackageCompilationError as exc:
            raise ProductionExecutionError(str(exc)) from exc
        return super().start(task_id, production_package=package)

    def _require_task(self, task_id: str) -> ProductionTask:
        task = self.tasks.get(task_id)
        if task is None:
            raise ProductionExecutionError(f"ProductionTask not found: {task_id}")
        return task
