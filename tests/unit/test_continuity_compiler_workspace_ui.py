from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt

from vscs.application.continuity_compiler import (
    ContinuityCompilationDraft,
    ContinuityCompilationStatus,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.presentation.widgets.continuity_compiler_workspace import ContinuityCompilerWorkspace


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
            lighting={"lighting_intent": "practical_motivated"},
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


class _Continuity:
    def __init__(
        self,
        draft: ContinuityCompilationDraft | None = None,
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


def _continuity_payload() -> dict:
    return {
        "current_shot_id": "SHT-001",
        "previous_shot_id": "",
        "previous_closing_state": "",
        "current_opening_state": "James is on the bridge.",
        "effective_opening_state": "James is on the bridge.",
        "current_closing_state": "James stands beside Cheryl.",
        "previous_asset_ids": [],
        "current_asset_ids": ["CAP-CHR-001"],
        "previous_screen_direction": "",
        "current_screen_direction": "neutral",
        "previous_lighting_continuity": "",
        "current_lighting_continuity": "Preserve bridge practicals.",
        "inheritance_mode": "series-entry",
        "continuity_conflicts": [],
    }


def test_continuity_tab_is_visible_and_requires_user_approval(qtbot) -> None:
    packages = _Packages()
    draft = ContinuityCompilationDraft(
        shot_id="SHT-001",
        source_package_id=packages.value.package_id,
        dependency_fingerprint="dependency",
        continuity=_continuity_payload(),
    )
    widget = ContinuityCompilerWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _Continuity(draft),  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.columnCount() == 8
    assert widget.package_table.horizontalHeaderItem(6).text() == "Continuity"
    assert widget.package_table.item(0, 6).text() == "Draft"
    assert widget.compiler_tabs.tabText(4) == "Continuity"
    assert widget.continuity_table.item(3, 1).text() == "James is on the bridge."
    assert widget.continuity_ready_button.isEnabled()
    assert "final approval" in widget.continuity_status.text().lower()


def test_stale_continuity_exposes_inheritance_refresh_and_preserves_notes(qtbot) -> None:
    packages = _Packages()
    draft = ContinuityCompilationDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-OLD",
        dependency_fingerprint="old-dependency",
        continuity=_continuity_payload(),
        production_notes="Preserve this continuity review note.",
        status=ContinuityCompilationStatus.DRAFT,
    )
    continuity = _Continuity(draft, current=False)
    widget = ContinuityCompilerWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        continuity,  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.item(0, 6).text() == "Draft / Stale"
    assert widget.continuity_refresh_button.isEnabled()
    assert widget.continuity_notes.isReadOnly()

    qtbot.mouseClick(widget.continuity_refresh_button, Qt.MouseButton.LeftButton)

    assert continuity.rebased
    assert widget.continuity_save_button.isEnabled()
    assert not widget.continuity_notes.isReadOnly()
    assert widget.continuity_notes.toPlainText() == "Preserve this continuity review note."
