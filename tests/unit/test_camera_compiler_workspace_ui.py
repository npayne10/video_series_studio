from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt

from vscs.application.camera_compiler import CameraCompilationDraft, CameraCompilationStatus
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.presentation.widgets.camera_compiler_workspace import CameraCompilerWorkspace


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
            shot={"title": "Arrival"},
            assets=(),
            camera={
                "camera_plan_id": "CAM-SHT-001",
                "shot_size": "wide",
                "angle": "eye_level",
                "movement": "track",
                "lens_family": "wide",
                "focal_length_mm": 35,
                "camera_height_m": 1.6,
                "screen_direction": "preserve_previous",
                "composition": "Readable geography",
                "focus_strategy": "Primary subject",
            },
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


class _Camera:
    def __init__(self, draft: CameraCompilationDraft | None = None, *, current: bool = True):
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


def test_camera_tab_is_visible_and_requires_user_approval(qtbot) -> None:
    packages = _Packages()
    draft = CameraCompilationDraft(
        shot_id="SHT-001",
        source_package_id=packages.value.package_id,
        source_fingerprint="source",
        camera=packages.value.camera,
    )
    widget = CameraCompilerWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _Camera(draft),  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.columnCount() == 6
    assert widget.package_table.horizontalHeaderItem(4).text() == "Camera"
    assert widget.package_table.item(0, 4).text() == "Draft"
    assert widget.compiler_tabs.tabText(2) == "Camera"
    assert widget.camera_table.item(0, 1).text() == "wide"
    assert widget.camera_ready_button.isEnabled()
    assert "approve" in widget.camera_status.text().lower()


def test_stale_camera_exposes_refresh_and_preserves_user_notes(qtbot) -> None:
    packages = _Packages()
    draft = CameraCompilationDraft(
        shot_id="SHT-001",
        source_package_id="PP-SHT-001-OLD",
        source_fingerprint="old-source",
        camera=packages.value.camera,
        production_notes="Preserve screen direction.",
        status=CameraCompilationStatus.DRAFT,
    )
    camera = _Camera(draft, current=False)
    widget = CameraCompilerWorkspace(
        _Projects(),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        _EmptyCompiler(),  # type: ignore[arg-type]
        camera,  # type: ignore[arg-type]
    )
    qtbot.addWidget(widget)

    assert widget.package_table.item(0, 4).text() == "Draft / Stale"
    assert widget.camera_refresh_button.isEnabled()
    assert widget.camera_notes.isReadOnly()

    qtbot.mouseClick(widget.camera_refresh_button, Qt.MouseButton.LeftButton)

    assert camera.rebased
    assert widget.camera_save_button.isEnabled()
    assert not widget.camera_notes.isReadOnly()
    assert widget.camera_notes.toPlainText() == "Preserve screen direction."
