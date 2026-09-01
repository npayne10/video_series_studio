from __future__ import annotations

from vscs.infrastructure.production_execution.segmented_backend import (
    LocalComfyUIProductionExecutionBackend,
    SegmentedLTX23V721ProductionPackageCompilationService,
)


def test_segmented_backend_exposes_profile_scoped_start_and_reconcile() -> None:
    assert "start_for_profile" in LocalComfyUIProductionExecutionBackend.__dict__
    assert "reconcile_for_profile" in LocalComfyUIProductionExecutionBackend.__dict__


def test_segmented_package_compiler_remains_current_authority_extension() -> None:
    assert "_comfyui_payload" in SegmentedLTX23V721ProductionPackageCompilationService.__dict__
