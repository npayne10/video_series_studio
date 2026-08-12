from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.style_compiler import StyleCompilationDraft, StyleCompilationStatus
from vscs.presentation.widgets.style_compiler_workspace import StyleCompilerWorkspace


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


class _EmptyCompiler:
    def draft(self, _shot_id: str):
        return None

    def is_current(self, _draft):
        return True


class _Style:
    def __init__(
        self,
        draft: StyleCompilationDraft | None = None,
        *,
        current: bool = True,
        missing: tuple[str, ...] = (),
    ) -> None:
        self.value = draft
        self.current = current
        self.missing = missing
        self.rebased = False

    def draft(self, _shot_id: str):
        return self.value

    def is_current(self, _draft):
        return self.current

    def missing_prerequisites(self, _shot_id: str):
        return self.missing

    def rebase_to_current_package(self, _shot_id: str):
        self.current = True
        self.rebased = True
        return self.value


def _style_payload() -> dict:
    return {
        "current_shot_id": "SHT-001",
        "declared_style": "grounded hard science-fiction realism",
        "declared_tone": "restrained",
        "camera_language": {"movement": "static"},
        "lighting_language": {"lighting_intent": "practical_motivated"},
        "continuity_language": {"inheritance_mode": "series-entry"},
        "environment_context": {"environment_plan_id": "ENV-BRIDGE"},
        "asset_ids": ["CAP-CHR-001"],
        "canonical_references": [],
        "source_policy": "governed-production-authority-only",
        "provider_neutral": True,
    }


def _widget(qtbot, style: _Style):
    packages = _Packages()
    widget = StyleCompilerWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        style,  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)
    return widget


def test_style_tab_is_visible_and_requires_user_approval(qtbot) -> None:
    draft = StyleCompilationDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-AAAA",
        dependency_fingerprint="dependency",
        style=_style_payload(),
    )
    widget = _widget(qtbot, _Style(draft))

    assert widget.package_table.columnCount() == 9
    assert widget.package_table.horizontalHeaderItem(7).text() == "Style"
    assert widget.package_table.item(0, 7).text() == "Draft"
    assert widget.compiler_tabs.tabText(5) == "Style"
    assert widget.style_table.item(0, 1).text() == "grounded hard science-fiction realism"
    assert widget.style_ready_button.isEnabled()
    assert "final approval" in widget.style_status.text().lower()


def test_style_final_approval_is_blocked_while_upstream_authority_is_draft(qtbot) -> None:
    draft = StyleCompilationDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-AAAA",
        dependency_fingerprint="dependency",
        style=_style_payload(),
    )
    widget = _widget(qtbot, _Style(draft, missing=("Assets", "Camera", "Continuity")))

    assert not widget.style_ready_button.isEnabled()
    assert "assets, camera, continuity" in widget.style_status.text().lower()
    assert widget.style_save_button.isEnabled()


def test_stale_style_exposes_refresh_and_preserves_notes(qtbot) -> None:
    draft = StyleCompilationDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-OLD",
        dependency_fingerprint="old-dependency",
        style=_style_payload(),
        production_notes="Preserve this style review note.",
        status=StyleCompilationStatus.DRAFT,
    )
    style = _Style(draft, current=False)
    widget = _widget(qtbot, style)

    assert widget.package_table.item(0, 7).text() == "Draft / Stale"
    assert widget.style_refresh_button.isEnabled()
    assert widget.style_notes.isReadOnly()

    qtbot.mouseClick(widget.style_refresh_button, Qt.MouseButton.LeftButton)

    assert style.rebased
    assert widget.style_save_button.isEnabled()
    assert not widget.style_notes.isReadOnly()
    assert widget.style_notes.toPlainText() == "Preserve this style review note."
