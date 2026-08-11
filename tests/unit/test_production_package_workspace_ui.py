from __future__ import annotations

from dataclasses import dataclass

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


class _Actions:
    def draft(self, _shot_id: str):
        return None


def test_workspace_exposes_action_story_editor_without_provider_prompt_controls(qtbot) -> None:
    widget = ProductionPackageWorkspace(
        _Projects(),  # type: ignore[arg-type]
        _Packages(),  # type: ignore[arg-type]
        _Actions(),  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.rowCount() == 1
    assert widget.package_table.item(0, 0).text() == "SHT-001"
    assert widget.create_button.text() == "Create from Shot"
    assert widget.ready_button.text() == "Mark Ready & Compile"
    assert widget.temporal_narrative.placeholderText().startswith("Example: James descends")
