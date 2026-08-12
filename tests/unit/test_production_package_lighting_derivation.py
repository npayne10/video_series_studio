"""Production Package Lighting derivation tests for Phase 19.4.5."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vscs.application.production_package import ProductionPackageService


@dataclass(frozen=True)
class _Integrated:
    package_id: str = "PIP-SHT-001-AAAA"
    shot_id: str = "SHT-001"
    review_id: str = "PRV-SHT-001"
    review_fingerprint: str = "review-fingerprint"
    package_fingerprint: str = "planning-fingerprint"

    def payload(self):
        return {
            "shot": {"shot_id": self.shot_id, "title": "Bridge Dialogue"},
            "assets": [],
            "camera": {"shot_size": "medium_close"},
            "lighting": {
                "lighting_plan_id": "LGT-SHT-001",
                "lighting_intent": "practical_motivated",
                "key_direction": "front_side",
                "key_quality": "soft",
                "color_temperature_k": 4300,
                "fill_level_percent": 50,
                "exposure_intent": "balanced",
                "source_strategy": "Motivated practical sources.",
                "shadow_strategy": "Soft directional modelling.",
                "subject_readability": "Natural facial readability.",
            },
            "environment": {"context": "bridge"},
        }


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Planning:
    def __init__(self) -> None:
        self.value = _Integrated()

    def require_current_package(self, _shot_id: str):
        return self.value

    def current_package(self, _shot_id: str):
        return self.value


def test_lighting_derivation_preserves_other_compiled_sections_and_history(tmp_path: Path) -> None:
    service = ProductionPackageService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        _Planning(),  # type: ignore[arg-type]
    )
    foundation = service.materialize("SHT-001")
    action = service.derive_action_performance(
        "SHT-001",
        {"temporal_narrative": "James speaks to Cheryl.", "provider_neutral": True},
    )
    camera = service.derive_camera(
        "SHT-001",
        {"governed": dict(action.camera), "production": {"provider_neutral": True}},
    )
    compiled = {
        "governed": dict(foundation.lighting),
        "production": {
            "lighting_intent": "practical_motivated",
            "color_temperature_k": 4300,
            "provider_neutral": True,
        },
    }

    derived = service.derive_lighting(
        "SHT-001",
        compiled,
        production_notes="Approved motivated bridge lighting.",
    )
    repeated = service.derive_lighting(
        "SHT-001",
        compiled,
        production_notes="Approved motivated bridge lighting.",
    )

    assert derived.package_id not in {foundation.package_id, action.package_id, camera.package_id}
    assert derived.action_performance == action.action_performance
    assert derived.camera == camera.camera
    assert derived.lighting == compiled
    assert derived.validation["lighting_complete"] is True
    assert derived.validation["lighting_review_notes"] == "Approved motivated bridge lighting."
    assert derived.provider_outputs == {}
    assert repeated == derived
    assert len(service.list_packages(shot_id="SHT-001")) == 4
