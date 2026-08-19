from datetime import UTC, datetime

import pytest

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    GeneratedMediaReviewActor,
    GeneratedMediaSelection,
    GeneratedMediaSelectionError,
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

NOW = datetime(2026, 8, 19, 15, 0, tzinfo=UTC)


class MemoryMediaRepository:
    def __init__(self, records: tuple[GeneratedMedia, ...]) -> None:
        self.records = {media.media_id: media for media in records}

    def get(self, media_id: str) -> GeneratedMedia | None:
        return self.records.get(media_id)

    def save(self, media: GeneratedMedia) -> GeneratedMedia:
        self.records[media.media_id] = media
        return media

    def list_for_production(self, production_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(item for item in self.records.values() if item.scope.production_id == production_id)

    def list_for_episode(self, production_id: str, episode_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_production(production_id)
            if item.scope.episode_id == episode_id
        )

    def list_for_scene(self, production_id: str, episode_id: str, scene_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_episode(production_id, episode_id)
            if item.scope.scene_id == scene_id
        )

    def list_for_shot(self, production_id: str, episode_id: str, scene_id: str, shot_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_scene(production_id, episode_id, scene_id)
            if item.scope.shot_id == shot_id
        )

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item for item in self.records.values() if item.scope.production_task_id == production_task_id
        )

    def list_for_execution(self, execution_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item for item in self.records.values() if item.provenance.execution_id == execution_id
        )


class MemorySelectionRepository:
    def __init__(self) -> None:
        self.records: dict[str, GeneratedMediaSelection] = {}

    def get(self, selection_id: str) -> GeneratedMediaSelection | None:
        return self.records.get(selection_id)

    def save(self, selection: GeneratedMediaSelection) -> GeneratedMediaSelection:
        self.records[selection.selection_id] = selection
        return selection

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMediaSelection, ...]:
        return tuple(
            item for item in self.records.values() if item.production_task_id == production_task_id
        )


def _generated(media_id: str, revision: int, *, task_id: str = "PT-20-12-001") -> GeneratedMedia:
    return GeneratedMedia(
        media_id=media_id,
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="XORIX",
            episode_id="EP-001",
            production_task_id=task_id,
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


def _approved(media_id: str, revision: int, *, task_id: str = "PT-20-12-001") -> GeneratedMedia:
    persistence = GeneratedMediaPersistenceService(MemoryMediaRepository((_generated(media_id, revision, task_id=task_id),)))
    media = persistence.get(media_id)
    assert media is not None
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


def _service(*media: GeneratedMedia) -> tuple[GeneratedMediaSelectionService, MemoryMediaRepository, MemorySelectionRepository]:
    media_repository = MemoryMediaRepository(tuple(media))
    selections = MemorySelectionRepository()
    return (
        GeneratedMediaSelectionService(
            GeneratedMediaPersistenceService(media_repository),
            selections,
        ),
        media_repository,
        selections,
    )


def _actor() -> GeneratedMediaReviewActor:
    return GeneratedMediaReviewActor(actor_id="editor-01", display_name="Editor One")


def test_only_approved_media_can_be_selected() -> None:
    service, _, _ = _service(_generated("GM-R1", 1))

    with pytest.raises(GeneratedMediaSelectionError, match="Only APPROVED"):
        service.select("GM-R1", selected_by=_actor(), reason="Choose candidate", now=NOW)


def test_first_selection_is_single_authoritative_candidate() -> None:
    first = _approved("GM-R1", 1)
    second = _approved("GM-R2", 2)
    service, _, _ = _service(first, second)

    selected = service.select("GM-R1", selected_by=_actor(), reason="Initial master", now=NOW)

    assert selected.selected_media_id == "GM-R1"
    assert selected.selected_revision == 1
    assert selected.selected_by == "human:editor-01"
    assert len(selected.history) == 1

    with pytest.raises(GeneratedMediaSelectionError, match="already has"):
        service.select("GM-R2", selected_by=_actor(), reason="Conflicting selection", now=NOW)


def test_supersession_requires_later_approved_revision_of_same_intent() -> None:
    first = _approved("GM-R1", 1)
    same_revision = _approved("GM-R1B", 1)
    other_task = _approved("GM-OTHER", 2, task_id="PT-OTHER")
    service, _, _ = _service(first, same_revision, other_task)
    service.select("GM-R1", selected_by=_actor(), reason="Initial", now=NOW)

    with pytest.raises(GeneratedMediaSelectionError, match="later"):
        service.supersede_and_select(
            "GM-R1B", selected_by=_actor(), reason="Not later", now=NOW
        )

    with pytest.raises(GeneratedMediaSelectionError, match="no current selection"):
        service.supersede_and_select(
            "GM-OTHER", selected_by=_actor(), reason="Wrong intent", now=NOW
        )


def test_supersede_and_select_preserves_history_and_marks_previous_superseded() -> None:
    first = _approved("GM-R1", 1)
    second = _approved("GM-R2", 2)
    service, media_repository, _ = _service(first, second)
    service.select("GM-R1", selected_by=_actor(), reason="Initial master", now=NOW)

    result = service.supersede_and_select(
        "GM-R2",
        selected_by=_actor(),
        reason="Revision two accepted as replacement",
        now=NOW,
    )

    assert result.selection.selected_media_id == "GM-R2"
    assert result.selection.selected_revision == 2
    assert tuple(event.selected_media_id for event in result.selection.history) == (
        "GM-R1",
        "GM-R2",
    )
    assert result.previous_media.state is GeneratedMediaState.SUPERSEDED
    assert result.previous_media.governance_history[-1].replacement_media_id == "GM-R2"
    assert result.replacement_media.state is GeneratedMediaState.APPROVED
    assert media_repository.records["GM-R1"].file.relative_path == first.file.relative_path


def test_candidates_are_returned_in_revision_order_without_deleting_history() -> None:
    first = _approved("GM-R1", 1)
    third = _approved("GM-R3", 3)
    second = _approved("GM-R2", 2)
    service, _, _ = _service(first, third, second)

    candidates = service.candidates_for(second)

    assert tuple(item.media_id for item in candidates) == ("GM-R1", "GM-R2", "GM-R3")
