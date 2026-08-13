from __future__ import annotations

from dataclasses import dataclass

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionDraft,
    UniversalProductionDescriptionStatus,
)
from vscs.presentation.widgets.universal_production_description_compiler_workspace import (
    UniversalProductionDescriptionCompilerWorkspace,
)


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
    project_directory = None


class _Packages:
    def __init__(self) -> None:
        self.planning = _Planning()
        self.value = ProductionPackage(
            package_id="PP-SHT-001-A",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="source",
            package_fingerprint="package",
            provenance=ProductionPackageProvenance("PIP", "source", "PRV", "review"),
            story_context={},
            shot={},
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


class _Universal:
    def __init__(
        self,
        draft: UniversalProductionDescriptionDraft | None = None,
        *,
        current: bool = True,
        missing: tuple[str, ...] = (),
        findings: tuple[str, ...] = (),
    ) -> None:
        self.value = draft
        self.current = current
        self.missing = missing
        self.findings = findings

    def draft(self, _shot_id: str):
        return self.value

    def is_current(self, _draft):
        return self.current

    def missing_prerequisites(self, _shot_id: str):
        return self.missing

    def consistency_findings(self, _shot_id: str):
        return self.findings


def _widget(qtbot, universal: _Universal):
    packages = _Packages()
    widget = UniversalProductionDescriptionCompilerWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        universal,  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)
    return widget


def _description() -> dict:
    return {
        "current_shot_id": "SHT-001",
        "shot": {"title": "Bridge Dialogue", "target_runtime_seconds": 20},
        "camera": {"shot_size": "medium_close", "movement": "static"},
        "universal_text": "SHOT: Bridge Dialogue\nCAMERA: static medium close",
        "source_policy": "approved-production-authority-only",
        "provider_neutral": True,
    }


def test_universal_tab_is_visible_and_requires_user_approval(qtbot) -> None:
    draft = UniversalProductionDescriptionDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-A",
        dependency_fingerprint="dependency",
        description=_description(),
    )
    widget = _widget(qtbot, _Universal(draft))

    preview = widget.universal_preview.toPlainText()
    assert widget.package_table.columnCount() == 11
    assert widget.package_table.horizontalHeaderItem(8).text() == "Universal"
    assert widget.package_table.horizontalHeaderItem(9).text() == "Provider"
    assert widget.package_table.item(0, 8).text() == "Draft"
    assert widget.compiler_tabs.tabText(6) == "Universal Description"
    assert widget.compiler_tabs.tabText(7) == "Provider Output"
    assert "SHOT\n" in preview
    assert "Title: Bridge Dialogue" in preview
    assert "CAMERA\n" in preview
    assert "Movement: static" in preview
    assert not preview.startswith("SHOT: {")
    assert widget.universal_ready_button.isEnabled()

    footer_texts = [label.text() for label in widget.findChildren(type(widget.universal_status))]
    assert any(
        text
        == "Later Phase 19.4 work will add final Production Package Validation to this same workspace."
        for text in footer_texts
    )


def test_universal_final_approval_is_blocked_until_upstream_ready(qtbot) -> None:
    draft = UniversalProductionDescriptionDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-A",
        dependency_fingerprint="dependency",
        description=_description(),
        status=UniversalProductionDescriptionStatus.DRAFT,
    )
    widget = _widget(qtbot, _Universal(draft, missing=("Continuity", "Style")))

    assert not widget.universal_ready_button.isEnabled()
    assert "continuity, style" in widget.universal_status.text().lower()
    assert widget.universal_save_button.isEnabled()


def test_universal_final_approval_is_blocked_by_consistency_findings(qtbot) -> None:
    description = {
        **_description(),
        "consistency_findings": [
            "Action & Performance places performers in an interior location, but Environment authority describes vacuum/orbital space."
        ],
    }
    draft = UniversalProductionDescriptionDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-A",
        dependency_fingerprint="dependency",
        description=description,
    )
    widget = _widget(
        qtbot,
        _Universal(draft, findings=(description["consistency_findings"][0],)),
    )

    assert widget.package_table.item(0, 8).text() == "Draft / Blocked"
    assert not widget.universal_ready_button.isEnabled()
    assert "consistency finding" in widget.universal_status.text().lower()
    assert "CONSISTENCY FINDINGS\n" in widget.universal_preview.toPlainText()


def test_provider_output_is_blocked_until_universal_authority_is_ready(qtbot) -> None:
    widget = _widget(qtbot, _Universal())
    assert widget.provider_selector.currentData() == "comfyui"
    assert not widget.provider_create_button.isEnabled()
    assert "blocked until the universal" in widget.provider_status.text().lower()
