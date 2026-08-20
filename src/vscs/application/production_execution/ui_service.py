"""Thin application facade for operator-facing production execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType

from .package_compilation import ProductionPackageStatus
from .retry_override import (
    GovernedRetryOverrideState,
    GovernedRetryOverrideStatus,
)
from .telemetry import ProductionTelemetrySnapshot


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

    def has_execution(self, task_id: str) -> bool: ...

    def telemetry(self, task_id: str) -> ProductionTelemetrySnapshot: ...

    def retry_override_status(self, task_id: str) -> GovernedRetryOverrideStatus: ...

    def authorize_retry(
        self,
        task_id: str,
        *,
        authorized_by: str,
        reason: str,
    ) -> GovernedRetryOverrideStatus: ...

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

    def has_execution(self, task_id: str) -> bool:
        normalized = self._task_id(task_id, "inspecting execution availability")
        return self.backend.has_execution(normalized)

    def telemetry(self, task_id: str) -> ProductionTelemetrySnapshot:
        normalized = self._task_id(task_id, "inspecting live production telemetry")
        return self.backend.telemetry(normalized)

    def retry_override_status(self, task_id: str) -> GovernedRetryOverrideStatus:
        normalized = self._task_id(task_id, "inspecting retry override authority")
        operation = getattr(self.backend, "retry_override_status", None)
        if operation is None:
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.BLOCKED,
                1,
                0,
                1,
                message="This execution backend does not support governed retry overrides.",
            )
        return operation(normalized)

    def authorize_retry(
        self,
        task_id: str,
        *,
        authorized_by: str,
        reason: str,
    ) -> GovernedRetryOverrideStatus:
        normalized = self._task_id(task_id, "authorizing an additional retry")
        operation = getattr(self.backend, "authorize_retry", None)
        if operation is None:
            raise ProductionExecutionError(
                "This execution backend does not support governed retry overrides."
            )
        return operation(normalized, authorized_by=authorized_by, reason=reason)

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        normalized = self._task_id(task_id, "inspecting its Production Package")
        status = self.backend.package_status(normalized, profile=profile)
        return self._block_if_execution_exists(normalized, status)

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        normalized = self._task_id(task_id, "compiling its Production Package")
        status = self.backend.compile_package(normalized, profile=profile)
        return self._block_if_execution_exists(normalized, status)

    def start(
        self,
        task_id: str,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        normalized = self._task_id(task_id, "starting production")
        if self.backend.has_execution(normalized):
            raise ProductionExecutionError(
                "ProductionTask already has an execution record. Use Refresh Execution Status "
                "to inspect it; retry or restart recovery must use governed execution authority."
            )
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

    def _block_if_execution_exists(
        self,
        task_id: str,
        status: ProductionPackageStatus,
    ) -> ProductionPackageStatus:
        if not self.backend.has_execution(task_id) or not status.executable:
            return status
        return replace(
            status,
            path=None,
            message=(
                f"{status.message} Start blocked because this ProductionTask already has an "
                "execution record; inspect execution status instead of creating a duplicate attempt."
            ),
        )

    @staticmethod
    def _task_id(task_id: str, action: str) -> str:
        normalized = task_id.strip()
        if not normalized:
            raise ProductionExecutionError(f"Select a ProductionTask before {action}")
        return normalized
