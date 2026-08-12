"""Phase 19.4.4 Camera Compiler tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.camera_compiler import (
    CameraCompilationStatus,
    CameraCompilerError,
    CameraCompilerService,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self) -> None:
        self.value = self._package("source-1", "PP-SHT-001-A")
        self.derived: dict | None = None
        self.notes = ""

    @staticmethod
    def _camera() -> dict:
        return {
            "camera_plan_id": "CAM-SHT-001",
            "shot_id": "SHT-001",
            "shot_size": "wide",
            "angle": "eye_level",
            "movement": "track",
            "lens_family": "wide",
            "focal_length_mm": 35,
            "camera_height_m": 1.6,
            "screen_direction": "preserve_previous",
            "composition": "Preserve readable geography.",
            "focus_strategy": "Hold primary subject focus.",
            "movement_notes": "Track at stable speed.",
            "continuity_notes": "Preserve previous screen direction.",
            "camera_constraints": ["No impossible acceleration"],
            "camera_profile_asset_id": "CAP-CAM-001",
        }

    @classmethod
    def _package(cls, source: str, package_id: str) -> ProductionPackage:
        return ProductionPackage(
            package_id=package_id,
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint=source,
            package_fingerprint=f"fingerprint-{source}",
            provenance=ProductionPackageProvenance("PIP-1", source, "PRV-1", "review"),
            story_context={},
            shot={},
            assets=(),
            camera=cls._camera(),
            lighting={},
            environment={},
            action_performance={"temporal_narrative": "Ship approaches."},
            continuity={},
            style={},
            dialogue=(),
            effects=(),
            references=(),
            universal_description={},
            provider_outputs={},
            validation={"action_performance_complete": True, "assets_complete": True},
            status=ProductionPackageStatus.COMPILING,
        )

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value

    def derive_camera(self, _shot_id: str, compiled, *, production_notes: str = ""):
        self.derived = compiled
        self.notes = production_notes
        return replace(self.value, camera=compiled)


def _service(tmp_path: Path):
    packages = _Packages()
    service = CameraCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
    )
    return service, packages


def test_create_seeds_governed_camera_without_invention(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    draft = service.create_from_current_package("sht-001")

    assert draft.shot_id == "SHT-001"
    assert draft.camera == packages.value.camera
    assert draft.production_notes == ""
    assert draft.status is CameraCompilationStatus.DRAFT


def test_ready_compilation_is_provider_neutral_and_preserves_camera_authority(
    tmp_path: Path,
) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "User approves restrained tracking movement.")
    ready = service.mark_ready("SHT-001")

    assert ready.status is CameraCompilationStatus.READY
    assert packages.derived is not None
    assert packages.derived["governed"]["camera_plan_id"] == "CAM-SHT-001"
    assert packages.derived["production"]["movement"] == "track"
    assert packages.derived["production"]["focal_length_mm"] == 35
    assert packages.derived["production"]["screen_direction"] == "preserve_previous"
    assert packages.derived["production"]["provider_neutral"] is True
    assert packages.notes == "User approves restrained tracking movement."


def test_ready_camera_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.mark_ready("SHT-001")

    with pytest.raises(CameraCompilerError, match="return to Draft"):
        service.save_notes("SHT-001", "Changed")

    draft = service.return_to_draft("SHT-001")
    assert draft.status is CameraCompilationStatus.DRAFT
    assert service.save_notes("SHT-001", "Changed").production_notes == "Changed"


def test_upstream_change_makes_camera_stale_and_refresh_preserves_notes(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "Preserve this user review note.")
    packages.value = packages._package("source-2", "PP-SHT-001-B")

    stale = service.draft("SHT-001")
    assert stale is not None
    assert not service.is_current(stale)
    with pytest.raises(CameraCompilerError, match="stale"):
        service.mark_ready("SHT-001")

    refreshed = service.rebase_to_current_package("SHT-001")
    assert service.is_current(refreshed)
    assert refreshed.source_package_id == "PP-SHT-001-B"
    assert refreshed.production_notes == "Preserve this user review note."


def test_incomplete_governed_camera_is_rejected_at_approval(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    packages.value = replace(packages.value, camera={"shot_size": "wide"})
    service.create_from_current_package("SHT-001")

    with pytest.raises(CameraCompilerError, match="incomplete"):
        service.mark_ready("SHT-001")
