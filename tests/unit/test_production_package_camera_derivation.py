from __future__ import annotations

from pathlib import Path

from vscs.application.production_package import ProductionPackageService
from vscs.application.story.planning_integration import IntegratedPlanningPackage


class _Planning:
    def __init__(self) -> None:
        self.package = IntegratedPlanningPackage(
            package_id="PIP-SHT-001-A",
            shot_id="SHT-001",
            review_id="PRV-SHT-001",
            review_fingerprint="review",
            package_fingerprint="source",
            payload_json=(
                '{"shot":{"title":"Arrival"},"assets":[],"camera":'
                '{"shot_size":"wide","angle":"eye_level","movement":"static",'
                '"lens_family":"wide","focal_length_mm":28,"camera_height_m":1.6,'
                '"screen_direction":"preserve_previous","composition":"geography",'
                '"focus_strategy":"deep"},"lighting":{},"environment":{}}'
            ),
        )

    def require_current_package(self, _shot_id: str):
        return self.package

    def current_package(self, _shot_id: str):
        return self.package


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


def test_camera_derivation_preserves_other_compiled_sections(tmp_path: Path) -> None:
    projects = _Projects(tmp_path)
    planning = _Planning()
    service = ProductionPackageService(projects, planning)  # type: ignore[arg-type]
    foundation = service.materialize("SHT-001")
    action = service.derive_action_performance("SHT-001", {"temporal_narrative": "Arrival."})
    compiled = {
        "governed": dict(foundation.camera),
        "production": {
            "shot_size": "wide",
            "movement": "static",
            "provider_neutral": True,
        },
    }

    camera = service.derive_camera("SHT-001", compiled, production_notes="Approved by user.")

    assert camera.package_id != action.package_id
    assert camera.action_performance == action.action_performance
    assert camera.camera == compiled
    assert camera.validation["camera_complete"] is True
    assert camera.validation["camera_review_notes"] == "Approved by user."
    assert foundation.camera["shot_size"] == "wide"
