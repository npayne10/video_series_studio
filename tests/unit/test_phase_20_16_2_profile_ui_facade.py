from pathlib import Path

from vscs.application.production_execution import (
    GovernedRetryOverrideState,
    GovernedRetryOverrideStatus,
    ProductionExecutionCandidate,
    ProductionExecutionResult,
    ProductionExecutionState,
    ProductionExecutionUiService,
    ProductionPackageCompilationState,
    ProductionPackageStatus,
    ProductionTelemetrySnapshot,
    ProductionTelemetryState,
)
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType


class _Backend:
    def __init__(self, package: Path) -> None:
        self.package = package
        self.profile_calls: list[tuple[str, str]] = []
        self.candidate = ProductionExecutionCandidate(
            production_id="XORIX",
            task_id="PT-PROFILE-UI",
            task_type=ProductionTaskType.VIDEO_GENERATION,
            task_state=ProductionTaskState.READY,
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
            resource_id="GPU-01",
            queue_entry_id="PQE-PT-PROFILE-UI",
            label="Video Generation — SHT-001",
        )

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        return (self.candidate,)

    def has_execution(self, task_id: str) -> bool:
        return False

    def has_execution_for_profile(self, task_id: str, *, profile: str) -> bool:
        self.profile_calls.append(("has", profile))
        return False

    def telemetry(self, task_id: str) -> ProductionTelemetrySnapshot:
        raise AssertionError("profile telemetry path expected")

    def telemetry_for_profile(self, task_id: str, *, profile: str) -> ProductionTelemetrySnapshot:
        self.profile_calls.append(("telemetry", profile))
        return ProductionTelemetrySnapshot(
            task_id=task_id,
            state=ProductionTelemetryState.FAILED,
            live=False,
            queue_state="durable-summary",
            message=profile,
        )

    def retry_override_status(self, task_id: str) -> GovernedRetryOverrideStatus:
        raise AssertionError("profile retry status path expected")

    def retry_override_status_for_profile(
        self, task_id: str, *, profile: str
    ) -> GovernedRetryOverrideStatus:
        self.profile_calls.append(("retry", profile))
        return GovernedRetryOverrideStatus(
            GovernedRetryOverrideState.NOT_REQUIRED,
            3,
            0,
            3,
            next_attempt_number=1,
            message=profile,
        )

    def authorize_retry(self, task_id: str, *, authorized_by: str, reason: str):  # type: ignore[no-untyped-def]
        raise AssertionError("profile retry authorization path expected")

    def authorize_retry_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        authorized_by: str,
        reason: str,
    ) -> GovernedRetryOverrideStatus:
        self.profile_calls.append(("authorize", profile))
        return self.retry_override_status_for_profile(task_id, profile=profile)

    def package_status(
        self, task_id: str, *, profile: str = "production"
    ) -> ProductionPackageStatus:
        self.profile_calls.append(("package", profile))
        return ProductionPackageStatus(
            task_id=task_id,
            state=ProductionPackageCompilationState.COMPILED,
            profile=profile,
            path=self.package,
            message="compiled",
        )

    def compile_package(
        self, task_id: str, *, profile: str = "production"
    ) -> ProductionPackageStatus:
        return self.package_status(task_id, profile=profile)

    def start(
        self, task_id: str, *, production_package: Path | None = None
    ) -> ProductionExecutionResult:
        raise AssertionError("profile start path expected")

    def start_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        self.profile_calls.append(("start", profile))
        return ProductionExecutionResult(
            candidate=self.candidate,
            state=ProductionExecutionState.SUBMITTED,
            execution_id="PEX-A001",
            message=profile,
        )

    def reconcile(self, task_id: str) -> ProductionExecutionResult:
        raise AssertionError("profile reconcile path expected")

    def reconcile_for_profile(self, task_id: str, *, profile: str) -> ProductionExecutionResult:
        self.profile_calls.append(("reconcile", profile))
        return ProductionExecutionResult(
            candidate=self.candidate,
            state=ProductionExecutionState.FAILED,
            message=profile,
        )


def test_package_selection_becomes_default_profile_context_for_legacy_workspace_calls(
    tmp_path: Path,
) -> None:
    package = tmp_path / "production_package.json"
    package.write_text("{}", encoding="utf-8")
    backend = _Backend(package)
    service = ProductionExecutionUiService(backend)

    status = service.package_status("PT-PROFILE-UI", profile="preview")
    assert status.profile == "preview"

    service.retry_override_status("PT-PROFILE-UI")
    service.telemetry("PT-PROFILE-UI")
    result = service.start("PT-PROFILE-UI")
    reconciled = service.reconcile("PT-PROFILE-UI")

    assert result.message == "preview"
    assert reconciled.message == "preview"
    assert ("retry", "preview") in backend.profile_calls
    assert ("telemetry", "preview") in backend.profile_calls
    assert ("start", "preview") in backend.profile_calls
    assert ("reconcile", "preview") in backend.profile_calls
