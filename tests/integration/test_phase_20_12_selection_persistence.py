from datetime import UTC, datetime, timedelta

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    GeneratedMediaReviewActor,
    GeneratedMediaSelectionService,
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

NOW = datetime(2026, 8, 19, 15, 30, tzinfo=UTC)


def _generated(media_id: str, revision: int) -> GeneratedMedia:
    return GeneratedMedia(
        media_id=media_id,
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="XORIX",
            episode_id="EP-001",
            production_task_id="PT-20-12-001",
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
    )


def _approve(media: GeneratedMedia, persistence: GeneratedMediaPersistenceService) -> GeneratedMedia:
    under_review = persistence.governance.submit_for_review(
        media,
        submitted_by="human:submitter",
        reason="Ready",
        occurred_at=NOW,
    )
    return persistence.governance.approve(
        under_review,
        reviewed_by="human:reviewer",
        reason="Approved",
        occurred_at=NOW,
    )


def test_selection_and_supersession_survive_repository_restart(tmp_path) -> None:
    media_root = tmp_path / "media"
    selection_root = tmp_path / "selections"
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(media_root))
    first = _approve(_generated("GM-20-12-R1", 1), persistence)
    second = _approve(_generated("GM-20-12-R2", 2), persistence)
    persistence.register(first)
    persistence.register(second)

    service = GeneratedMediaSelectionService(
        persistence,
        JsonGeneratedMediaSelectionRepository(selection_root),
    )
    actor = GeneratedMediaReviewActor(actor_id="editor-01", display_name="Editor One")
    initial = service.select(
        first.media_id,
        selected_by=actor,
        reason="Initial approved production master",
        now=NOW,
    )
    replaced = service.supersede_and_select(
        second.media_id,
        selected_by=actor,
        reason="Revision two replaces revision one",
        now=NOW + timedelta(minutes=5),
    )

    assert initial.selected_media_id == first.media_id
    assert replaced.selection.selected_media_id == second.media_id
    assert replaced.previous_media.state is GeneratedMediaState.SUPERSEDED

    restarted_media = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(media_root))
    restarted_selections = JsonGeneratedMediaSelectionRepository(selection_root)
    restarted_service = GeneratedMediaSelectionService(restarted_media, restarted_selections)

    restored_second = restarted_media.get(second.media_id)
    restored_first = restarted_media.get(first.media_id)
    assert restored_second is not None
    assert restored_first is not None
    selection = restarted_service.get_for_media(restored_second)
    assert selection is not None
    assert selection.selected_media_id == second.media_id
    assert selection.selected_revision == 2
    assert tuple(event.selected_media_id for event in selection.history) == (
        first.media_id,
        second.media_id,
    )
    assert selection.history[-1].actor == "human:editor-01"
    assert selection.history[-1].reason == "Revision two replaces revision one"
    assert restored_first.state is GeneratedMediaState.SUPERSEDED
    assert restored_first.governance_history[-1].replacement_media_id == second.media_id
    assert restored_second.state is GeneratedMediaState.APPROVED
    assert restarted_selections.list_for_task("PT-20-12-001") == (selection,)
