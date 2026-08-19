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
    for media_id, production_id, episode_id, task_id, shot_id in (
        ("GM-UI-001", "XORIX", "EP-001", "PT-VIDEO-GENERATION-00000001", "SHT-001"),
        ("GM-UI-002", "XORIX", "EP-002", "PT-VIDEO-GENERATION-00000002", "SHT-010"),
        ("GM-UI-003", "DEMO", "EP-001", "PT-VIDEO-GENERATION-00000003", "SHT-100"),
    ):
        persistence.register(
            GeneratedMedia(
                media_id=media_id,
                kind=GeneratedMediaKind.VIDEO,
                scope=GeneratedMediaScope(
                    production_id=production_id,
                    episode_id=episode_id,
                    production_task_id=task_id,
                    shot_id=shot_id,
                ),
                provenance=GeneratedMediaProvenance(
                    execution_id=f"PEX-{media_id}",
                    provider_id="LOCAL-COMFYUI-01",
                    provider_job_id=f"prompt-{media_id}",
                ),
                file=GeneratedMediaFile(relative_path=f"generated_media/{media_id}.mp4"),
                technical_metadata=(("technical_validation.status", "passed"),),
            )
        )
    return GeneratedMediaUiService(
        media_repository_factory=lambda: JsonGeneratedMediaRepository(media_root),
        selection_repository_factory=lambda: JsonGeneratedMediaSelectionRepository(selection_root),
    )


def test_workspace_requires_project_service(
    qtbot: object,
    qapp: QApplication,
) -> None:
    widget = GeneratedMediaWorkspaceWidget(lambda: None)
    qtbot.addWidget(widget)  # type: ignore[attr-defined]

    widget.refresh()

    assert "Open a project" in widget.summary.text()
    assert widget.media_table.rowCount() == 0
    assert widget.production_filter.currentText() == "All Productions"
    assert not widget.approve_button.isEnabled()


def test_workspace_browses_all_media_without_typing_ids(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    widget = GeneratedMediaWorkspaceWidget(lambda: service)
    qtbot.addWidget(widget)  # type: ignore[attr-defined]

    widget.refresh()

    assert widget.production_filter.count() == 3
    assert widget.production_filter.currentText() == "All Productions"
    assert widget.media_table.rowCount() == 3
    assert "Showing 3 of 3" in widget.summary.text()


def test_workspace_cascades_production_episode_and_task_filters(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    widget = GeneratedMediaWorkspaceWidget(lambda: service)
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    widget.refresh()

    widget.production_filter.setCurrentIndex(widget.production_filter.findData("XORIX"))
    qapp.processEvents()

    assert widget.media_table.rowCount() == 2
    assert widget.episode_filter.count() == 3
    assert widget.task_filter.count() == 3

    widget.episode_filter.setCurrentIndex(widget.episode_filter.findData("EP-002"))
    qapp.processEvents()

    assert widget.media_table.rowCount() == 1
    assert widget.task_filter.count() == 2
    assert "SHT-010" in widget.task_filter.itemText(1)


def test_workspace_exposes_readable_context_and_stable_ids(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    widget = GeneratedMediaWorkspaceWidget(lambda: service)
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    widget.refresh()

    widget.production_filter.setCurrentIndex(widget.production_filter.findData("XORIX"))
    widget.episode_filter.setCurrentIndex(widget.episode_filter.findData("EP-001"))
    qapp.processEvents()

    assert widget.media_table.rowCount() == 1
    assert widget.media_table.item(0, 0).text() == "XORIX"
    assert widget.media_table.item(0, 3).text() == "SHT-001"
    assert "Video" in widget.media_table.item(0, 4).text()
    assert widget.media_table.item(0, 8).text() == "passed"
    widget.media_table.selectRow(0)
    qapp.processEvents()

    assert "SHT-001" in widget.summary.text()
    assert "PEX-GM-UI-001" in widget.provenance.toPlainText()
    assert "GM-UI-001" in widget.identifiers.toPlainText()
    assert "PT-VIDEO-GENERATION-00000001" in widget.identifiers.toPlainText()
    assert "GM-UI-001" in widget.candidates.toPlainText()
    assert widget.submit_button.isEnabled()
