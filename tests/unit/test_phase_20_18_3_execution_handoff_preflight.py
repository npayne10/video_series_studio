"""Phase 20.18.3 Scheduling -> Production Execution handoff/preflight acceptance."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from vscs.application.production_execution import (
    ProductionExecutionCandidate,
    ProductionExecutionPreflightState,
    ProductionExecutionUiService,
    ProductionPackageCompilationState,
    ProductionPackageStatus,
)
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType
from vscs.presentation.widgets.production_execution_workspace import ProductionExecutionWorkspace


class _PreflightBackend:
    def __init__(self, package_path: Path) -> None:
        self.package_path = package_path
        self.package_state = ProductionPackageCompilationState.NOT_COMPILED
        self.execution_exists = False
        self.candidate = ProductionExecutionCandidate(
            production_id="VSCS-TEST",
            task_id="PT-20-18-3-001",
            task_type=ProductionTaskType.VIDEO_GENERATION,
            task_state=ProductionTaskState.READY,
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
            resource_id="GPU-01",
            queue_entry_id="PQE-PT-20-18-3-001",
            label="Video Generation — SHT-001",
        )

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        return (self.candidate,)

    def has_execution(self, _task_id: str) -> bool:
        return self.execution_exists

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        path = self.package_path if self.package_state is ProductionPackageCompilationState.COMPILED else None
        return ProductionPackageStatus(
            task_id=task_id,
            state=self.package_state,
            profile=profile,
            path=path,
            authority_fingerprint="authority-v1",
            package_fingerprint=(
                "package-v1"
                if self.package_state is ProductionPackageCompilationState.COMPILED
                else None
            ),
            message=self.package_state.value,
        )

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        self.package_path.parent.mkdir(parents=True, exist_ok=True)
        self.package_path.write_text("{}", encoding="utf-8")
        self.package_state = ProductionPackageCompilationState.COMPILED
        return self.package_status(task_id, profile=profile)

    def retry_override_status(self, _task_id: str):
        raise RuntimeError("Retry override is outside Phase 20.18.3 acceptance")


def test_approved_scheduled_handoff_requires_package_before_ready(tmp_path: Path) -> None:
    backend = _PreflightBackend(tmp_path / "package.json")
    service = ProductionExecutionUiService(backend)  # type: ignore[arg-type]

    preflight = service.preflight("PT-20-18-3-001")

    assert preflight.state is ProductionExecutionPreflightState.PACKAGE_REQUIRED
    assert not preflight.ready
    assert preflight.package_status is not None
    assert preflight.package_status.state is ProductionPackageCompilationState.NOT_COMPILED
    assert any(check.code == "schedule.current_approved_queue" and check.passed for check in preflight.checks)
    assert any(check.code == "task.ready" and check.passed for check in preflight.checks)
    assert any(check.code == "package.current_executable" and not check.passed for check in preflight.checks)


def test_compiled_current_package_completes_preflight(tmp_path: Path) -> None:
    backend = _PreflightBackend(tmp_path / "package.json")
    service = ProductionExecutionUiService(backend)  # type: ignore[arg-type]
    service.compile_package("PT-20-18-3-001")

    preflight = service.preflight("PT-20-18-3-001")

    assert preflight.state is ProductionExecutionPreflightState.READY
    assert preflight.ready
    assert all(check.passed for check in preflight.checks)


def test_stale_package_blocks_execution_preflight(tmp_path: Path) -> None:
    backend = _PreflightBackend(tmp_path / "package.json")
    backend.package_state = ProductionPackageCompilationState.STALE
    service = ProductionExecutionUiService(backend)  # type: ignore[arg-type]

    preflight = service.preflight("PT-20-18-3-001")

    assert preflight.state is ProductionExecutionPreflightState.BLOCKED
    assert not preflight.ready
    assert "not current and executable" in preflight.message


def test_existing_profile_execution_is_visible_in_preflight(tmp_path: Path) -> None:
    backend = _PreflightBackend(tmp_path / "package.json")
    backend.compile_package("PT-20-18-3-001")
    backend.execution_exists = True
    service = ProductionExecutionUiService(backend)  # type: ignore[arg-type]

    preflight = service.preflight("PT-20-18-3-001")

    assert preflight.state is ProductionExecutionPreflightState.EXECUTION_EXISTS
    assert not preflight.ready
    assert any(check.code == "execution.new_attempt_available" and not check.passed for check in preflight.checks)


def test_workspace_exposes_handoff_preflight_and_package_transition(
    qtbot,
    tmp_path: Path,
) -> None:
    backend = _PreflightBackend(tmp_path / "package.json")
    service = ProductionExecutionUiService(backend)  # type: ignore[arg-type]
    workspace = ProductionExecutionWorkspace(lambda: service)
    qtbot.addWidget(workspace)

    workspace.refresh()

    assert workspace.table.rowCount() == 1
    assert workspace.table.horizontalHeaderItem(7).text() == "Preflight"
    assert workspace.table.horizontalHeaderItem(8).text() == "Package"
    assert workspace.table.item(0, 7).text() == "PACKAGE-REQUIRED"
    assert workspace.table.item(0, 8).text() == "NOT_COMPILED"
    assert "PACKAGE REQUIRED 1" in workspace.summary.text()

    workspace.table.selectRow(0)
    assert "PACKAGE-REQUIRED" in workspace.preflight_state.text()
    assert "schedule queue" in workspace.details.toPlainText()
    assert not workspace.start_button.isEnabled()
    assert workspace.compile_package_button.isEnabled()

    qtbot.mouseClick(workspace.compile_package_button, Qt.MouseButton.LeftButton)

    assert workspace.table.item(0, 7).text() == "READY"
    assert workspace.table.item(0, 8).text() == "COMPILED"
    assert "Preflight: READY" in workspace.preflight_state.text()
    assert workspace.start_button.isEnabled()
