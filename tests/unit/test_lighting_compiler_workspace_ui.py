from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt

from vscs.application.lighting_compiler import (
    LightingCompilationDraft,
    LightingCompilationStatus,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.presentation.widgets.lighting_compiler_workspace import LightingCompilerWorkspace


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
                "PIP-SHT-001-AAAA", "source", "PRV-SHT-001", "review"
            ),
            story_context={"shot_id": "SHT-001"},
            shot={"title": "Bridge Dialogue"},
            assets=(),
            camera={"shot_size": "medium_close"},
            lighting={
                "lighting_plan_id": "LGT-SHT-001",
                "lighting_intent": "practical_motivated",
                "key_direction": "front_side",
                "key_quality": "soft",
                "color_temperature_k": 4300,
                "fill_level_percent": 50,
                "exposure_intent": "balanced",
                "source_strategy": "Use motivated practical sources.",
                "shadow_strategy": "Preserve soft directional modelling.",
                "subject_readability": "Maintain natural facial readability.",
                "continuity_notes": "Preserve bridge lighting state.",
            },
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


class _EmptyCompiler:
    def draft(self, _shot_id: str):
        return None

    def is_current(self, _draft):
        return True


class _Lighting:
    def __init__(
        self,
        draft: LightingCompilationDraft | None = None,
        *,
        current: bool = True,
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


def test_lighting_tab_is_visible_and_requires_user_approval(qtbot) -> None:
    packages = _Packages()
    draft = LightingCompilationDraft(
        shot_id="SHT-001",
        source_package_id=packages.value.package_id,
        source_fingerprint="source",
        lighting=packages.value.lighting,
    )
    widget = LightingCompilerWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _Lighting(draft),  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.columnCount() == 7
    assert widget.package_table.horizontalHeaderItem(5).text() == "Lighting"
    assert widget.package_table.item(0, 5).text() == "Draft"
    assert widget.compiler_tabs.tabText(3) == "Lighting"
    assert widget.lighting_table.item(0, 1).text() == "practical_motivated"
    assert widget.lighting_ready_button.isEnabled()
    assert "approve" in widget.lighting_status.text().lower()


def test_stale_lighting_exposes_refresh_and_preserves_user_notes(qtbot) -> None:
    packages = _Packages()
    draft = LightingCompilationDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-OLD",
        source_fingerprint="old-source",
        lighting=packages.value.lighting,
        production_notes="Preserve motivated light direction.",
        status=LightingCompilationStatus.DRAFT,
    )
    lighting = _Lighting(draft, current=False)
    widget = LightingCompilerWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        lighting,  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.item(0, 5).text() == "Draft / Stale"
    assert widget.lighting_refresh_button.isEnabled()
    assert widget.lighting_notes.isReadOnly()

    qtbot.mouseClick(widget.lighting_refresh_button, Qt.MouseButton.LeftButton)

    assert lighting.rebased
    assert widget.lighting_save_button.isEnabled()
    assert not widget.lighting_notes.isReadOnly()
    assert widget.lighting_notes.toPlainText() == "Preserve motivated light direction."
