"""Phase 19.4.3 Asset Compiler tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.asset_compiler import (
    AssetCompilationStatus,
    AssetCompilerError,
    AssetCompilerService,
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
        self.derived: tuple[dict, ...] | None = None
        self.notes = ""

    @staticmethod
    def _package(source: str, package_id: str) -> ProductionPackage:
        return ProductionPackage(
            package_id=package_id,
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint=source,
            package_fingerprint=f"fingerprint-{source}",
            provenance=ProductionPackageProvenance("PIP-1", source, "PRV-1", "review"),
            story_context={},
            shot={},
            assets=(
                {
                    "binding": {
                        "binding_id": "AB-SHT-001-001",
                        "asset_id": "CAP-CHR-001",
                        "role": "Commander",
                        "requirement": "James is visible in the Shot",
                        "expected_category": "character",
                    },
                    "resolution": {
                        "asset_id": "CAP-CHR-001",
                        "canonical_reference": "references/james.png",
                        "fingerprint": {"checksum": "asset-checksum"},
                    },
                },
            ),
            camera={},
            lighting={},
            environment={},
            action_performance={"temporal_narrative": "James enters."},
            continuity={},
            style={},
            dialogue=(),
            effects=(),
            references=(),
            universal_description={},
            provider_outputs={},
            validation={"action_performance_complete": True},
            status=ProductionPackageStatus.COMPILING,
        )

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value

    def derive_assets(self, _shot_id: str, compiled, *, production_notes: str = ""):
        self.derived = compiled
        self.notes = production_notes
        return replace(self.value, assets=compiled)


def _service(tmp_path: Path):
    packages = _Packages()
    service = AssetCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
    )
    return service, packages


def test_create_seeds_only_governed_package_assets(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    draft = service.create_from_current_package("sht-001")

    assert draft.shot_id == "SHT-001"
    assert draft.assets == packages.value.assets
    assert draft.production_notes == ""
    assert draft.status is AssetCompilationStatus.DRAFT


def test_ready_compilation_is_provider_neutral_and_preserves_governed_source(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "Keep canonical bridge uniform and rank insignia visible.")
    ready = service.mark_ready("SHT-001")

    assert ready.status is AssetCompilationStatus.READY
    assert packages.derived is not None
    compiled = packages.derived[0]
    assert compiled["binding"]["binding_id"] == "AB-SHT-001-001"
    assert compiled["resolution"]["asset_id"] == "CAP-CHR-001"
    assert compiled["production"]["role"] == "Commander"
    assert compiled["production"]["canonical_reference"] == "references/james.png"
    assert compiled["production"]["dependency_checksum"] == "asset-checksum"
    assert compiled["production"]["provider_neutral"] is True
    assert packages.notes.startswith("Keep canonical bridge uniform")


def test_ready_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.mark_ready("SHT-001")

    with pytest.raises(AssetCompilerError, match="return to Draft"):
        service.save_notes("SHT-001", "Changed")

    draft = service.return_to_draft("SHT-001")
    assert draft.status is AssetCompilationStatus.DRAFT
    assert service.save_notes("SHT-001", "Changed").production_notes == "Changed"


def test_upstream_change_makes_asset_draft_stale_and_refresh_preserves_notes(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "Preserve this human review note.")
    packages.value = packages._package("source-2", "PP-SHT-001-B")

    stale = service.draft("SHT-001")
    assert stale is not None
    assert not service.is_current(stale)
    with pytest.raises(AssetCompilerError, match="stale"):
        service.mark_ready("SHT-001")

    refreshed = service.rebase_to_current_package("SHT-001")
    assert service.is_current(refreshed)
    assert refreshed.source_package_id == "PP-SHT-001-B"
    assert refreshed.production_notes == "Preserve this human review note."


def test_malformed_asset_input_is_rejected_during_compile(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    packages.value = replace(packages.value, assets=({"binding": [], "resolution": {}},))
    service.create_from_current_package("SHT-001")

    with pytest.raises(AssetCompilerError, match="malformed"):
        service.mark_ready("SHT-001")
