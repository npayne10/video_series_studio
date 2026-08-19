from datetime import UTC, datetime
from pathlib import Path

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
    GeneratedMediaState,
)
from vscs.infrastructure.generated_media import (
    JsonGeneratedMediaRepository,
    JsonGeneratedMediaSelectionRepository,
)

NOW = datetime(2026, 8, 19, 17, 30, tzinfo=UTC)


def _media(media_id: str, revision: int) -> GeneratedMedia:
    return GeneratedMedia(
        media_id=media_id,
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="XORIX",
            episode_id="EP-001",
            production_task_id="PT-20-14-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id=f"PEX-{media_id}",
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id=f"prompt-{media_id}",
        ),
        file=GeneratedMediaFile(relative_path=f"generated_media/{media_id}.mp4"),
        revision=revision,
        technical_metadata=(("technical_validation.status", "passed"),),
        created_at=NOW,
    )


def _service(tmp_path: Path) -> tuple[GeneratedMediaUiService, GeneratedMediaPersistenceService]:
    media_root = tmp_path / "media"
    selection_root = tmp_path / "selections"
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(media_root))
    service = GeneratedMediaUiService(
        media_repository_factory=lambda: JsonGeneratedMediaRepository(media_root),
        selection_repository_factory=lambda: JsonGeneratedMediaSelectionRepository(selection_root),
    )
    return service, persistence


def _approve_direct(media: GeneratedMedia, persistence: GeneratedMediaPersistenceService) -> GeneratedMedia:
    reviewed = persistence.governance.submit_for_review(
        media,
        submitted_by="human:submitter",
        reason="Ready",
        occurred_at=NOW,
    )
    return persistence.governance.approve(
        reviewed,
        reviewed_by="human:reviewer",
        reason="Approved",
        occurred_at=NOW,
    )


def test_workspace_list_exposes_authoritative_media_state(tmp_path: Path) -> None:
    service, persistence = _service(tmp_path)
    persistence.register(_media("GM-R1", 1))
    persistence.register(_media("GM-R2", 2))

    items = service.list_for_production("XORIX")

    assert tuple(item.media_id for item in items) == ("GM-R1", "GM-R2")
    assert tuple(item.revision for item in items) == (1, 2)
    assert all(item.technical_status == "passed" for item in items)
    assert not any(item.selected for item in items)


def test_workspace_review_and_selection_commands_use_governed_services(tmp_path: Path) -> None:
    service, persistence = _service(tmp_path)
    persistence.register(_media("GM-R1", 1))

    submitted = service.submit_for_review(
        "GM-R1",
        actor_id="producer-01",
        display_name="Producer One",
        reason="Ready for review",
    )
    assert submitted.media.state is GeneratedMediaState.UNDER_REVIEW

    approved = service.approve(
        "GM-R1",
        actor_id="reviewer-01",
        display_name="Reviewer One",
        reason="Approved for production",
    )
    assert approved.media.state is GeneratedMediaState.APPROVED

    selected = service.select(
        "GM-R1",
        actor_id="editor-01",
        display_name="Editor One",
        reason="Authoritative shot output",
    )
    assert selected.selection is not None
    assert selected.selection.selected_media_id == "GM-R1"
    assert selected.selection.selected_by == "human:editor-01"

    listed = service.list_for_production("XORIX")
    assert listed[0].selected


def test_workspace_supersession_preserves_revision_and_governance_history(tmp_path: Path) -> None:
    service, persistence = _service(tmp_path)
    first = _approve_direct(_media("GM-R1", 1), persistence)
    second = _approve_direct(_media("GM-R2", 2), persistence)
    persistence.register(first)
    persistence.register(second)

    service.select(
        "GM-R1",
        actor_id="editor-01",
        display_name="Editor One",
        reason="Initial selection",
    )
    replacement = service.supersede_and_select(
        "GM-R2",
        actor_id="editor-01",
        display_name="Editor One",
        reason="Revision two replaces revision one",
    )

    assert replacement.selection is not None
    assert replacement.selection.selected_media_id == "GM-R2"
    detail_first = service.detail("GM-R1")
    assert detail_first.media.state is GeneratedMediaState.SUPERSEDED
    assert detail_first.media.governance_history[-1].replacement_media_id == "GM-R2"
