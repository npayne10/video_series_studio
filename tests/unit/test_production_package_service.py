"""Phase 19.4.1 Production Package foundation tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from vscs.application.production_package import ProductionPackageError, ProductionPackageService


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
                    "binding": {"binding_id": "B-1"},
                    "resolution": {
                        "asset_id": "CAP-SHP-001",
                        "canonical_reference": "references/mauritania.png",
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
        self.current = True

    def require_current_package(self, _shot_id: str):
        if not self.current:
            raise RuntimeError("not current")
        return self.value

    def current_package(self, _shot_id: str):
        return self.value if self.current else None


def _service(tmp_path: Path):
    planning = _Planning()
    service = ProductionPackageService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        planning,  # type: ignore[arg-type]
    )
    return service, planning


def test_materializes_renderer_neutral_foundation(tmp_path: Path) -> None:
    service, _planning = _service(tmp_path)
    package = service.materialize("SHT-001")

    assert package.package_id.startswith("PP-SHT-001-")
    assert package.shot["title"] == "Arrival"
    assert package.camera["movement"] == "push_in"
    assert package.references[0]["canonical_reference"] == "references/mauritania.png"
    assert package.action_performance == {}
    assert package.universal_description == {}
    assert package.provider_outputs == {}
    assert package.validation["provider_neutral"] is True
    assert package.validation["specialist_compilation_complete"] is False


def test_materialization_is_idempotent_and_persistent(tmp_path: Path) -> None:
    service, _planning = _service(tmp_path)
    first = service.materialize("SHT-001")
    second = service.materialize("SHT-001")

    assert second == first
    assert service.list_packages() == (first,)
    raw = json.loads(service.package_file.read_text(encoding="utf-8"))
    assert raw["schema_version"] == "1.0"
    assert len(raw["production_packages"]) == 1


def test_new_integrated_planning_preserves_package_history(tmp_path: Path) -> None:
    service, planning = _service(tmp_path)
    first = service.materialize("SHT-001")
    planning.value = _Integrated(
        package_id="PIP-SHT-001-BBBB",
        package_fingerprint="planning-fingerprint-2",
        review_fingerprint="review-fingerprint-2",
    )
    second = service.materialize("SHT-001")

    assert second.package_id != first.package_id
    assert len(service.list_packages(shot_id="SHT-001")) == 2
    assert service.current_package("SHT-001") == second
    assert not service.is_current(first)


def test_no_current_planning_means_no_current_production_package(tmp_path: Path) -> None:
    service, planning = _service(tmp_path)
    package = service.materialize("SHT-001")
    planning.current = False

    assert service.current_package("SHT-001") is None
    assert not service.is_current(package)
    with pytest.raises(ProductionPackageError, match="No current Production Package"):
        service.require_current_package("SHT-001")


def test_invalid_integrated_payload_is_rejected(tmp_path: Path) -> None:
    service, planning = _service(tmp_path)

    class Broken(_Integrated):
        def payload(self):
            return {"shot": [], "assets": [], "camera": {}, "lighting": {}, "environment": {}}

    planning.value = Broken()
    with pytest.raises(ProductionPackageError, match="shot"):
        service.materialize("SHT-001")
