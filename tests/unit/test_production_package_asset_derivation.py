"""Production Package Asset derivation tests for Phase 19.4.3."""

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
            "shot": {"shot_id": self.shot_id, "title": "Arrival"},
            "assets": [
                {
                    "binding": {
                        "binding_id": "AB-1",
                        "role": "Commander",
                        "requirement": "James visible",
                        "asset_id": "CAP-CHR-001",
                    },
                    "resolution": {
                        "asset_id": "CAP-CHR-001",
                        "canonical_reference": "references/james.png",
                    },
                }
            ],
            "camera": {"movement": "push_in"},
            "lighting": {"intent": "naturalistic"},
            "environment": {"context": "interior"},
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


def test_asset_derivation_preserves_other_compiled_sections_and_history(tmp_path: Path) -> None:
    service = ProductionPackageService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        _Planning(),  # type: ignore[arg-type]
    )
    foundation = service.materialize("SHT-001")
    action = service.derive_action_performance(
        "SHT-001",
        {"temporal_narrative": "James enters the bridge.", "provider_neutral": True},
    )
    compiled_assets = (
        {
            "binding": dict(action.assets[0]["binding"]),
            "resolution": dict(action.assets[0]["resolution"]),
            "production": {
                "asset_id": "CAP-CHR-001",
                "role": "Commander",
                "provider_neutral": True,
            },
        },
    )

    derived = service.derive_assets(
        "SHT-001",
        compiled_assets,
        production_notes="Identity reviewed.",
    )
    repeated = service.derive_assets(
        "SHT-001",
        compiled_assets,
        production_notes="Identity reviewed.",
    )

    assert derived.package_id not in {foundation.package_id, action.package_id}
    assert derived.assets == compiled_assets
    assert derived.action_performance == action.action_performance
    assert derived.camera == foundation.camera
    assert derived.validation["action_performance_complete"] is True
    assert derived.validation["assets_complete"] is True
    assert derived.validation["asset_review_notes"] == "Identity reviewed."
    assert derived.references[0]["canonical_reference"] == "references/james.png"
    assert derived.provider_outputs == {}
    assert repeated == derived
    assert len(service.list_packages(shot_id="SHT-001")) == 3
