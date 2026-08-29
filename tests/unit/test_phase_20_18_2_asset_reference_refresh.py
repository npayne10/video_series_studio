from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt

from vscs.application.action_performance import ActionPerformanceDraft
from vscs.application.asset_compiler import (
    AssetCompilationDraft,
    AssetCompilationStatus,
    AssetCompilerService,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.presentation.widgets.production_package_workspace import ProductionPackageWorkspace


class _Projects:
    is_project_open = True

    def __init__(self, root: Path | None = None) -> None:
        self.project_directory = root


class _Integrated:
    shot_id = "SHT-001"


class _Planning:
    def list_packages(self):
        return (_Integrated(),)

    def is_current(self, _package):
        return True


class _Packages:
    def __init__(self, assets: tuple[dict, ...]) -> None:
        self.planning = _Planning()
        self.value = self._package(assets)

    @staticmethod
    def _package(assets: tuple[dict, ...]) -> ProductionPackage:
        return ProductionPackage(
            package_id="PP-SHT-001-CURRENT",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="same-planning-source",
            package_fingerprint="package-current",
            provenance=ProductionPackageProvenance(
                "PIP-SHT-001",
                "same-planning-source",
                "PRV-SHT-001",
                "review",
            ),
            story_context={},
            shot={},
            assets=assets,
            camera={},
            lighting={},
            environment={},
            action_performance={},
            continuity={},
            style={},
            dialogue=(),
            effects=(),
            references=(),
            universal_description={},
            provider_outputs={},
            validation={"foundation_complete": True},
            status=ProductionPackageStatus.COMPILING,
        )

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value


class _Actions:
    def draft(self, _shot_id: str) -> ActionPerformanceDraft | None:
        return None

    def is_current(self, _draft) -> bool:
        return True


class _AssetFacade:
    def __init__(self, draft: AssetCompilationDraft) -> None:
        self.value = draft
        self.current = True
        self.refresh_count = 0

    def draft(self, _shot_id: str):
        return self.value

    def is_current(self, _draft) -> bool:
        return self.current

    def rebase_to_current_package(self, _shot_id: str):
        self.refresh_count += 1
        return self.value


def _asset(reference_path: str, *, nested: bool = False) -> dict:
    resolution: dict = {"asset_id": "CAP-CHR-001"}
    if nested:
        resolution["references"] = [
            {
                "reference_id": "REF-JAMES-16X9",
                "file_path": reference_path,
                "reference_type": "image",
                "role": "primary",
                "checksum": "checksum",
            }
        ]
    else:
        resolution["canonical_reference"] = reference_path
    return {
        "binding": {
            "binding_id": "AB-SHT-001-001",
            "asset_id": "CAP-CHR-001",
            "role": "Commander",
            "requirement": "James visible",
        },
        "resolution": resolution,
    }


def test_asset_refresh_reloads_current_package_even_when_source_fingerprint_is_unchanged(
    tmp_path: Path,
) -> None:
    packages = _Packages((_asset("references/james-old.png"),))
    service = AssetCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
    )
    created = service.create_from_current_package("SHT-001")
    assert created.assets[0]["resolution"]["canonical_reference"] == "references/james-old.png"

    packages.value = replace(
        packages.value,
        package_id="PP-SHT-001-REFRESHED",
        package_fingerprint="package-refreshed",
        assets=(_asset("references/james-16x9.png"),),
    )

    refreshed = service.rebase_to_current_package("SHT-001")

    assert refreshed.source_fingerprint == "same-planning-source"
    assert refreshed.source_package_id == "PP-SHT-001-REFRESHED"
    assert refreshed.assets[0]["resolution"]["canonical_reference"] == "references/james-16x9.png"


def test_assets_ui_displays_nested_current_canonical_references_and_allows_explicit_refresh(
    qtbot,
) -> None:
    packages = _Packages((_asset("references/james-16x9.png", nested=True),))
    draft = AssetCompilationDraft(
        shot_id="SHT-001",
        source_package_id=packages.value.package_id,
        source_fingerprint=packages.value.source_fingerprint,
        assets=packages.value.assets,
        status=AssetCompilationStatus.DRAFT,
    )
    assets = _AssetFacade(draft)
    widget = ProductionPackageWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _Actions(),  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.asset_table.horizontalHeaderItem(4).text() == "Canonical References"
    assert widget.asset_table.item(0, 4).text() == "primary: references/james-16x9.png"
    assert widget.asset_refresh_button.isEnabled()

    qtbot.mouseClick(widget.asset_refresh_button, Qt.MouseButton.LeftButton)

    assert assets.refresh_count == 1
