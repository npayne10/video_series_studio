from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt

from vscs.application.action_performance import ActionPerformanceDraft, ActionPerformanceStatus
from vscs.application.asset_compiler import AssetCompilationDraft, AssetCompilationStatus
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.presentation.widgets.production_package_workspace import ProductionPackageWorkspace


@dataclass(frozen=True)
class _Integrated:
    shot_id: str = "SHT-001"


class _Planning:
    def list_packages(self):
        return (_Integrated(),)

    def is_current(self, _package):
        return True


class _Projects:
    is_project_open = True


class _Packages:
    def __init__(self) -> None:
        self.planning = _Planning()
        self.value = ProductionPackage(
            package_id="PP-SHT-001-AAAA",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="source",
            package_fingerprint="package",
            provenance=ProductionPackageProvenance(
                "PIP-SHT-001-AAAA",
                "source",
                "PRV-SHT-001",
                "review",
            ),
            story_context={"shot_id": "SHT-001"},
            shot={"title": "Arrival"},
            assets=(
                {
                    "binding": {
                        "binding_id": "AB-SHT-001-001",
                        "asset_id": "CAP-CHR-001",
                        "role": "Commander",
                        "requirement": "James visible",
                    },
                    "resolution": {
                        "asset_id": "CAP-CHR-001",
                        "canonical_reference": "references/james.png",
                    },
                },
            ),
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
            status=ProductionPackageStatus.FOUNDATION,
        )

    def materialize(self, _shot_id: str):
        return self.value

    def current_package(self, _shot_id: str):
        return self.value


class _Actions:
    def __init__(
        self, draft: ActionPerformanceDraft | None = None, *, current: bool = True
    ) -> None:
        self.value = draft
        self.current = current
        self.rebased = False

    def draft(self, _shot_id: str):
        return self.value

    def is_current(self, _draft):
        return self.current

    def rebase_to_current_package(self, _shot_id: str):
        self.current = True
        self.rebased = True
        return self.value


class _Assets:
    def __init__(
        self, draft: AssetCompilationDraft | None = None, *, current: bool = True
    ) -> None:
        self.value = draft
        self.current = current
        self.rebased = False

    def draft(self, _shot_id: str):
        return self.value

    def is_current(self, _draft):
        return self.current

    def rebase_to_current_package(self, _shot_id: str):
        self.current = True
        self.rebased = True
        return self.value


def test_workspace_exposes_action_and_asset_compilers_without_provider_controls(qtbot) -> None:
    widget = ProductionPackageWorkspace(
        _Projects(),  # type: ignore[arg-type]
        _Packages(),  # type: ignore[arg-type]
        _Actions(),  # type: ignore[arg-type]
        _Assets(),  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.rowCount() == 1
    assert widget.package_table.item(0, 0).text() == "SHT-001"
    assert widget.create_button.text() == "Create from Shot"
    assert widget.ready_button.text() == "Mark Ready & Compile"
    assert widget.temporal_narrative.placeholderText().startswith("Example: James descends")
    assert widget.compiler_tabs.tabText(0) == "Action & Performance"
    assert widget.compiler_tabs.tabText(1) == "Assets"
    assert widget.asset_create_button.text() == "Create from Package"
    assert widget.package_table.item(0, 3).text() == "Not started"


def test_stale_action_draft_exposes_refresh_recovery_and_preserves_content(qtbot) -> None:
    draft = ActionPerformanceDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-OLD",
        source_fingerprint="old-source",
        temporal_narrative="Mauritania emerges from hyperspace and Xorix becomes visible.",
        spoken_content='"We have arrived at Xorix."',
        performance_direction="Restrained sense of wonder.",
        opening_state="First shot.",
        closing_state="Xorix fills the viewport.",
        timing_notes="Target runtime: 20 seconds",
        status=ActionPerformanceStatus.DRAFT,
    )
    actions = _Actions(draft, current=False)
    widget = ProductionPackageWorkspace(
        _Projects(),  # type: ignore[arg-type]
        _Packages(),  # type: ignore[arg-type]
        actions,  # type: ignore[arg-type]
        _Assets(),  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.item(0, 2).text() == "Draft / Stale"
    assert widget.refresh_source_button.isEnabled()
    assert widget.temporal_narrative.isReadOnly()
    assert "preserve this authored content" in widget.action_status.text()

    qtbot.mouseClick(widget.refresh_source_button, Qt.MouseButton.LeftButton)

    assert actions.rebased
    assert not widget.temporal_narrative.isReadOnly()
    assert widget.save_button.isEnabled()
    assert widget.temporal_narrative.toPlainText() == draft.temporal_narrative


def test_asset_compiler_displays_governed_assets_and_stale_recovery(qtbot) -> None:
    packages = _Packages()
    draft = AssetCompilationDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-OLD",
        source_fingerprint="old-source",
        assets=packages.value.assets,
        production_notes="Preserve canonical identity.",
        status=AssetCompilationStatus.DRAFT,
    )
    assets = _Assets(draft, current=False)
    widget = ProductionPackageWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _Actions(),  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.item(0, 3).text() == "Draft / Stale"
    assert widget.asset_table.rowCount() == 1
    assert widget.asset_table.item(0, 1).text() == "CAP-CHR-001"
    assert widget.asset_table.item(0, 2).text() == "Commander"
    assert widget.asset_refresh_button.isEnabled()
    assert widget.asset_notes.isReadOnly()

    qtbot.mouseClick(widget.asset_refresh_button, Qt.MouseButton.LeftButton)

    assert assets.rebased
    assert widget.asset_save_button.isEnabled()
    assert not widget.asset_notes.isReadOnly()
    assert widget.asset_notes.toPlainText() == "Preserve canonical identity."
