"""Thin application facade for operator-facing production execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType

from .package_compilation import ProductionPackageStatus


class ProductionExecutionError(RuntimeError):
    """Raised when a production execution command cannot proceed safely."""


class ProductionExecutionState(StrEnum):
    """Operator-facing execution state without replacing provider or queue authority."""

    READY = "ready"
    PREPARING = "preparing"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ProductionExecutionCandidate:
    """One scheduled ProductionTask that can be inspected from the execution workspace."""

    production_id: str
    task_id: str
    task_type: ProductionTaskType
    task_state: ProductionTaskState
    episode_id: str
    scene_id: str | None
    shot_id: str | None
    resource_id: str
    queue_entry_id: str
    label: str


@dataclass(frozen=True, slots=True)
class ProductionExecutionResult:
    """Current operator view of one provider execution and ingestion result."""

    candidate: ProductionExecutionCandidate
    state: ProductionExecutionState
    provider_id: str | None = None
    execution_id: str | None = None
    provider_job_id: str | None = None
    progress: float | None = None
    generated_media_ids: tuple[str, ...] = ()
    media_output_directory: str | None = None
    message: str = ""

    @property
    def terminal(self) -> bool:
        return self.state in {
            ProductionExecutionState.COMPLETED,
            ProductionExecutionState.FAILED,
            ProductionExecutionState.CANCELLED,
        }


class ProductionExecutionBackend(Protocol):
    """Infrastructure boundary used by the desktop execution workspace."""

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]: ...

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus: ...

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus: ...

    def start(
        self,
        task_id: str,
        *,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult: ...

    def reconcile(self, task_id: str) -> ProductionExecutionResult: ...


class ProductionExecutionUiService:
    """Provider-neutral UI facade; infrastructure retains live provider composition."""

    def __init__(self, backend: ProductionExecutionBackend) -> None:
        self.backend = backend

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        return self.backend.candidates()

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        normalized = self._task_id(task_id, "inspecting its Production Package")
        return self.backend.package_status(normalized, profile=profile)

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        normalized = self._task_id(task_id, "compiling its Production Package")
        return self.backend.compile_package(normalized, profile=profile)

    def start(
        self,
        task_id: str,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        normalized = self._task_id(task_id, "starting production")
        package: Path | None = None
        if production_package is not None:
            package = Path(production_package).expanduser().resolve(strict=False)
            if not package.is_file():
                raise ProductionExecutionError(f"Production package does not exist: {package}")
            if package.suffix.casefold() != ".json":
                raise ProductionExecutionError("Production package must be a JSON file")
        return self.backend.start(normalized, production_package=package)

    def reconcile(self, task_id: str) -> ProductionExecutionResult:
        normalized = self._task_id(task_id, "refreshing execution")
        return self.backend.reconcile(normalized)

    @staticmethod
    def _task_id(task_id: str, action: str) -> str:
        normalized = task_id.strip()
        if not normalized:
            raise ProductionExecutionError(f"Select a ProductionTask before {action}")
        return normalized
