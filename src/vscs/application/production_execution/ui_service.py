"""Thin application facade for operator-facing production execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Protocol, cast

from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType

from .package_compilation import ProductionPackageStatus
from .profiles import normalize_execution_profile
from .retry_override import GovernedRetryOverrideState, GovernedRetryOverrideStatus
from .telemetry import ProductionTelemetrySnapshot


class ProductionExecutionError(RuntimeError):
    """Raised when a production execution command cannot proceed safely."""


class ProductionExecutionState(StrEnum):
    READY = "ready"
    PREPARING = "preparing"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ProductionExecutionCandidate:
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
    """Backward-compatible infrastructure boundary used by the desktop workspace."""

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


class _HasExecutionForProfile(Protocol):
    def __call__(self, task_id: str, *, profile: str) -> bool: ...


class _TelemetryForProfile(Protocol):
    def __call__(self, task_id: str, *, profile: str) -> ProductionTelemetrySnapshot: ...


class _RetryOverrideStatusForProfile(Protocol):
    def __call__(self, task_id: str, *, profile: str) -> GovernedRetryOverrideStatus: ...


class _AuthorizeRetryForProfile(Protocol):
    def __call__(
        self,
        task_id: str,
        *,
        profile: str,
        authorized_by: str,
        reason: str,
    ) -> GovernedRetryOverrideStatus: ...


class _StartForProfile(Protocol):
    def __call__(
        self,
        task_id: str,
        *,
        profile: str,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult: ...


class _ReconcileForProfile(Protocol):
    def __call__(self, task_id: str, *, profile: str) -> ProductionExecutionResult: ...


class _RetryOverrideStatusOperation(Protocol):
    def __call__(self, task_id: str) -> GovernedRetryOverrideStatus: ...


class _AuthorizeRetryOperation(Protocol):
    def __call__(
        self,
        task_id: str,
        *,
        authorized_by: str,
        reason: str,
    ) -> GovernedRetryOverrideStatus: ...


class ProductionExecutionUiService:
    """Provider-neutral UI facade with optional profile-scoped execution authority."""

    def __init__(self, backend: ProductionExecutionBackend) -> None:
        self.backend = backend
        self._selected_profiles: dict[str, str] = {}

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        return self.backend.candidates()

    def has_execution(self, task_id: str, *, profile: str | None = None) -> bool:
        normalized = self._task_id(task_id, "inspecting execution availability")
        execution_profile = self._resolve_profile(normalized, profile)
        raw = getattr(self.backend, "has_execution_for_profile", None)
        if raw is not None:
            return cast(_HasExecutionForProfile, raw)(normalized, profile=execution_profile)
        return self.backend.has_execution(normalized)

    def telemetry(
        self,
        task_id: str,
        *,
        profile: str | None = None,
    ) -> ProductionTelemetrySnapshot:
        normalized = self._task_id(task_id, "inspecting live production telemetry")
        execution_profile = self._resolve_profile(normalized, profile)
        raw = getattr(self.backend, "telemetry_for_profile", None)
        if raw is not None:
            return cast(_TelemetryForProfile, raw)(normalized, profile=execution_profile)
        return self.backend.telemetry(normalized)

    def retry_override_status(
        self,
        task_id: str,
        *,
        profile: str | None = None,
    ) -> GovernedRetryOverrideStatus:
        normalized = self._task_id(task_id, "inspecting retry override authority")
        execution_profile = self._resolve_profile(normalized, profile)
        scoped = getattr(self.backend, "retry_override_status_for_profile", None)
        if scoped is not None:
            return cast(_RetryOverrideStatusForProfile, scoped)(
                normalized,
                profile=execution_profile,
            )
        raw_operation = getattr(self.backend, "retry_override_status", None)
        if raw_operation is None:
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.BLOCKED,
                1,
                0,
                1,
                message="This execution backend does not support governed retry overrides.",
            )
        return cast(_RetryOverrideStatusOperation, raw_operation)(normalized)

    def authorize_retry(
        self,
        task_id: str,
        *,
        authorized_by: str,
        reason: str,
        profile: str | None = None,
    ) -> GovernedRetryOverrideStatus:
        normalized = self._task_id(task_id, "authorizing an additional retry")
        execution_profile = self._resolve_profile(normalized, profile)
        scoped = getattr(self.backend, "authorize_retry_for_profile", None)
        if scoped is not None:
            return cast(_AuthorizeRetryForProfile, scoped)(
                normalized,
                profile=execution_profile,
                authorized_by=authorized_by,
                reason=reason,
            )
        raw_operation = getattr(self.backend, "authorize_retry", None)
        if raw_operation is None:
            raise ProductionExecutionError(
                "This execution backend does not support governed retry overrides."
            )
        return cast(_AuthorizeRetryOperation, raw_operation)(
            normalized,
            authorized_by=authorized_by,
            reason=reason,
        )

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        normalized = self._task_id(task_id, "inspecting its Production Package")
        execution_profile = normalize_execution_profile(profile)
        self._selected_profiles[normalized] = execution_profile
        status = self.backend.package_status(normalized, profile=execution_profile)
        return self._block_if_execution_exists(normalized, execution_profile, status)

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        normalized = self._task_id(task_id, "compiling its Production Package")
        execution_profile = normalize_execution_profile(profile)
        self._selected_profiles[normalized] = execution_profile
        status = self.backend.compile_package(normalized, profile=execution_profile)
        return self._block_if_execution_exists(normalized, execution_profile, status)

    def start(
        self,
        task_id: str,
        production_package: Path | None = None,
        *,
        profile: str | None = None,
    ) -> ProductionExecutionResult:
        normalized = self._task_id(task_id, "starting production")
        execution_profile = self._resolve_profile(normalized, profile)
        if self.has_execution(normalized, profile=execution_profile):
            raise ProductionExecutionError(
                f"ProductionTask already has an execution record for the {execution_profile} "
                "profile that is active, successful, or has exhausted its profile-scoped "
                "execution authority. Inspect execution status first."
            )
        package: Path | None = None
        if production_package is not None:
            package = Path(production_package).expanduser().resolve(strict=False)
            if not package.is_file():
                raise ProductionExecutionError(f"Production package does not exist: {package}")
            if package.suffix.casefold() != ".json":
                raise ProductionExecutionError("Production package must be a JSON file")
        scoped = getattr(self.backend, "start_for_profile", None)
        if scoped is not None:
            return cast(_StartForProfile, scoped)(
                normalized,
                profile=execution_profile,
                production_package=package,
            )
        return self.backend.start(normalized, production_package=package)

    def reconcile(
        self,
        task_id: str,
        *,
        profile: str | None = None,
    ) -> ProductionExecutionResult:
        normalized = self._task_id(task_id, "refreshing execution")
        execution_profile = self._resolve_profile(normalized, profile)
        scoped = getattr(self.backend, "reconcile_for_profile", None)
        if scoped is not None:
            return cast(_ReconcileForProfile, scoped)(normalized, profile=execution_profile)
        return self.backend.reconcile(normalized)

    def _block_if_execution_exists(
        self,
        task_id: str,
        profile: str,
        status: ProductionPackageStatus,
    ) -> ProductionPackageStatus:
        if not self.has_execution(task_id, profile=profile) or not status.executable:
            return status
        return replace(
            status,
            path=None,
            message=(
                f"{status.message} Start blocked for {profile} because this profile has active, "
                "successful, or exhausted execution authority."
            ),
        )

    def _resolve_profile(self, task_id: str, profile: str | None) -> str:
        if profile is not None:
            normalized = normalize_execution_profile(profile)
            self._selected_profiles[task_id] = normalized
            return normalized
        return self._selected_profiles.get(task_id, "production")

    @staticmethod
    def _task_id(task_id: str, action: str) -> str:
        normalized = task_id.strip()
        if not normalized:
            raise ProductionExecutionError(f"Select a ProductionTask before {action}")
        return normalized
