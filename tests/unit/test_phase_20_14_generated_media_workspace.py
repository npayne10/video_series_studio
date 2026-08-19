from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    GeneratedMediaUiService,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
)
from vscs.infrastructure.generated_media import (
    JsonGeneratedMediaRepository,
    JsonGeneratedMediaSelectionRepository,
)
from vscs.presentation.widgets.generated_media_workspace import GeneratedMediaWorkspaceWidget


def _service(tmp_path: Path) -> GeneratedMediaUiService:
    media_root = tmp_path / "media"
    selection_root = tmp_path / "selections"
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(media_root))
    persistence.register(
        GeneratedMedia(
            media_id="GM-UI-001",
            kind=GeneratedMediaKind.VIDEO,
            scope=GeneratedMediaScope(
                production_id="XORIX",
                episode_id="EP-001",
                production_task_id="PT-UI-001",
            ),
            provenance=GeneratedMediaProvenance(
                execution_id="PEX-UI-001",
                provider_id="LOCAL-COMFYUI-01",
                provider_job_id="prompt-ui-001",
            ),
            file=GeneratedMediaFile(relative_path="generated_media/GM-UI-001.mp4"),
            technical_metadata=(("technical_validation.status", "passed"),),
        )
    )
    return GeneratedMediaUiService(
        media_repository_factory=lambda: JsonGeneratedMediaRepository(media_root),
        selection_repository_factory=lambda: JsonGeneratedMediaSelectionRepository(selection_root),
    )


def test_workspace_requires_project_service_and_production_id(
    qtbot: object,
    qapp: QApplication,
) -> None:
    widget = GeneratedMediaWorkspaceWidget(lambda: None)
    qtbot.addWidget(widget)  # type: ignore[attr-defined]

    widget.refresh()

    assert "Open a project" in widget.summary.text()
    assert widget.media_table.rowCount() == 0
    assert not widget.approve_button.isEnabled()


def test_workspace_browses_media_and_exposes_detail(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    widget = GeneratedMediaWorkspaceWidget(lambda: service)
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    widget.production_id.setText("XORIX")

    widget.refresh()

    assert widget.media_table.rowCount() == 1
    assert widget.media_table.item(0, 0).text() == "GM-UI-001"
    assert widget.media_table.item(0, 5).text() == "passed"
    widget.media_table.selectRow(0)
    qapp.processEvents()

    assert "GM-UI-001" in widget.summary.text()
    assert "PEX-UI-001" in widget.provenance.toPlainText()
    assert "GM-UI-001" in widget.candidates.toPlainText()
    assert widget.submit_button.isEnabled()
