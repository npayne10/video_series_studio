from dataclasses import replace
from datetime import UTC, datetime

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    GeneratedMediaSelection,
    GeneratedMediaSelectionEvent,
    ProductionTaskCompletionReconciliationService,
)
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskLifecycleService,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
    GeneratedMediaState,
)

NOW = datetime(2026, 8, 19, 17, 0, tzinfo=UTC)
FINGERPRINT = "authority-fingerprint-20-13"


class MemoryTaskRepository:
    def __init__(self, task: ProductionTask) -> None:
        self.records = {task.task_id: task}
        self.save_count = 0

    def get(self, task_id: str) -> ProductionTask | None:
        return self.records.get(task_id)

    def save(self, task: ProductionTask) -> ProductionTask:
        self.save_count += 1
        self.records[task.task_id] = task
        return task

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        return tuple(
            item for item in self.records.values() if item.production_id == production_id
        )


class MemoryMediaRepository:
    def __init__(self, records: tuple[GeneratedMedia, ...]) -> None:
        self.records = {media.media_id: media for media in records}

    def get(self, media_id: str) -> GeneratedMedia | None:
        return self.records.get(media_id)

    def save(self, media: GeneratedMedia) -> GeneratedMedia:
        self.records[media.media_id] = media
        return media

    def list_for_production(self, production_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item for item in self.records.values() if item.scope.production_id == production_id
        )

    def list_for_episode(self, production_id: str, episode_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_production(production_id)
            if item.scope.episode_id == episode_id
        )

    def list_for_scene(
        self, production_id: str, episode_id: str, scene_id: str
    ) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_episode(production_id, episode_id)
            if item.scope.scene_id == scene_id
        )

    def list_for_shot(
        self, production_id: str, episode_id: str, scene_id: str, shot_id: str
    ) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_scene(production_id, episode_id, scene_id)
            if item.scope.shot_id == shot_id
        )

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.records.values()
            if item.scope.production_task_id == production_task_id
        )

    def list_for_execution(self, execution_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.records.values()
            if item.provenance.execution_id == execution_id
        )


class MemorySelectionRepository:
    def __init__(self, records: tuple[GeneratedMediaSelection, ...] = ()) -> None:
        self.records = {selection.selection_id: selection for selection in records}

    def get(self, selection_id: str) -> GeneratedMediaSelection | None:
        return self.records.get(selection_id)

    def save(self, selection: GeneratedMediaSelection) -> GeneratedMediaSelection:
        self.records[selection.selection_id] = selection
        return selection

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMediaSelection, ...]:
        return tuple(
            sorted(
                (
                    selection
                    for selection in self.records.values()
                    if selection.production_task_id == production_task_id
                ),
                key=lambda selection: selection.selection_id,
            )
        )


def _task(
    *,
    state: ProductionTaskState = ProductionTaskState.READY,
    expected_outputs: tuple[str, ...] = ("video/shot",),
) -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-13-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SHT-001",
            revision=1,
            fingerprint=FINGERPRINT,
            approved=True,
            approved_by="human:producer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=expected_outputs,
        state=state,
        metadata=(("existing", "preserved"),),
    )


def _approved_media(
    media_id: str = "GM-20-13-001",
    *,
    kind: GeneratedMediaKind = GeneratedMediaKind.VIDEO,
    revision: int = 1,
    fingerprint: str = FINGERPRINT,
) -> GeneratedMedia:
    repository = MemoryMediaRepository(())
    persistence = GeneratedMediaPersistenceService(repository)
    generated = GeneratedMedia(
        media_id=media_id,
        kind=kind,
        scope=GeneratedMediaScope(
            production_id="XORIX",
            episode_id="EP-001",
            production_task_id="PT-20-13-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id=f"PEX-{media_id}",
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id=f"prompt-{media_id}",
            attributes=(("authority_fingerprint", fingerprint),),
        ),
        file=GeneratedMediaFile(relative_path=f"generated_media/{media_id}.mp4"),
        revision=revision,
        technical_metadata=(("technical_validation.status", "passed"),),
    )
    reviewed = persistence.governance.submit_for_review(
        generated,
        submitted_by="human:submitter",
        reason="Ready for review",
        occurred_at=NOW,
    )
    return persistence.governance.approve(
        reviewed,
        reviewed_by="human:reviewer",
        reason="Accepted",
        occurred_at=NOW,
    )


def _selection(media: GeneratedMedia) -> GeneratedMediaSelection:
    event = GeneratedMediaSelectionEvent(
        previous_media_id=None,
        selected_media_id=media.media_id,
        selected_revision=media.revision,
        actor="human:selector",
        reason="Authoritative production choice",
        occurred_at=NOW,
    )
    return GeneratedMediaSelection(
        selection_id="GMS-20-13-VIDEO",
        production_id=media.scope.production_id,
        episode_id=media.scope.episode_id,
        production_task_id=media.scope.production_task_id,
        kind=media.kind,
        selected_media_id=media.media_id,
        selected_revision=media.revision,
        selected_by=event.actor,
        reason=event.reason,
        selected_at=NOW,
        history=(event,),
    )


def _service(
    task: ProductionTask,
    media: tuple[GeneratedMedia, ...] = (),
    selections: tuple[GeneratedMediaSelection, ...] = (),
) -> tuple[ProductionTaskCompletionReconciliationService, MemoryTaskRepository]:
    tasks = MemoryTaskRepository(task)
    return (
        ProductionTaskCompletionReconciliationService(
            lifecycle=ProductionTaskLifecycleService(tasks),
            media=GeneratedMediaPersistenceService(MemoryMediaRepository(media)),
            selections=MemorySelectionRepository(selections),
        ),
        tasks,
    )


def test_provider_media_without_authoritative_selection_does_not_complete_task() -> None:
    media = _approved_media()
    service, tasks = _service(_task(), (media,))

    result = service.reconcile("PT-20-13-001", now=NOW)

    assert not result.completed
    assert result.task.state is ProductionTaskState.READY
    assert {finding.code for finding in result.assessment.findings} == {
        "missing-authoritative-selection"
    }
    assert tasks.save_count == 0


def test_ready_task_completes_from_selected_approved_media_using_existing_lifecycle() -> None:
    media = _approved_media()
    service, tasks = _service(_task(), (media,), (_selection(media),))

    result = service.reconcile("PT-20-13-001", now=NOW)

    assert result.completed
    assert result.task.state is ProductionTaskState.COMPLETED
    assert tuple(transition.previous_state for transition in result.transitions) == (
        ProductionTaskState.READY,
        ProductionTaskState.RUNNING,
    )
    assert tuple(transition.current_state for transition in result.transitions) == (
        ProductionTaskState.RUNNING,
        ProductionTaskState.COMPLETED,
    )
    metadata = dict(result.task.metadata)
    assert metadata["existing"] == "preserved"
    assert metadata["completion_reconciliation.status"] == "completed"
    assert metadata["completion_reconciliation.output.001.media_id"] == media.media_id
    assert metadata["completion_reconciliation.output.001.selection_id"] == "GMS-20-13-VIDEO"
    assert tasks.save_count == 1


def test_running_task_uses_only_running_to_completed_transition() -> None:
    media = _approved_media()
    service, _ = _service(
        _task(state=ProductionTaskState.RUNNING),
        (media,),
        (_selection(media),),
    )

    result = service.reconcile("PT-20-13-001", now=NOW)

    assert result.completed
    assert len(result.transitions) == 1
    assert result.transitions[0].previous_state is ProductionTaskState.RUNNING
    assert result.transitions[0].current_state is ProductionTaskState.COMPLETED


def test_selected_media_from_different_authority_does_not_complete_task() -> None:
    media = _approved_media(fingerprint="different-authority")
    service, tasks = _service(_task(), (media,), (_selection(media),))

    result = service.reconcile("PT-20-13-001", now=NOW)

    assert not result.completed
    assert {finding.code for finding in result.assessment.findings} == {
        "production-authority-fingerprint-mismatch"
    }
    assert tasks.save_count == 0


def test_unsupported_output_contract_is_explicitly_blocking() -> None:
    service, _ = _service(_task(expected_outputs=("provider-specific/blob",)))

    result = service.reconcile("PT-20-13-001", now=NOW)

    assert not result.completed
    assert {finding.code for finding in result.assessment.findings} == {
        "unsupported-output-contract"
    }


def test_multiple_contracts_for_same_media_kind_are_rejected_as_ambiguous() -> None:
    service, _ = _service(_task(expected_outputs=("video/shot", "video/proxy")))

    result = service.reconcile("PT-20-13-001", now=NOW)

    assert not result.completed
    assert {finding.code for finding in result.assessment.findings} == {
        "ambiguous-output-contract-kind"
    }


def test_completed_task_reconciliation_is_idempotent() -> None:
    media = _approved_media()
    service, tasks = _service(_task(), (media,), (_selection(media),))
    first = service.reconcile("PT-20-13-001", now=NOW)
    save_count = tasks.save_count

    second = service.reconcile("PT-20-13-001", now=NOW)

    assert first.completed
    assert second.completed
    assert second.already_completed
    assert second.transitions == ()
    assert tasks.save_count == save_count


def test_non_executable_task_state_is_not_force_completed() -> None:
    media = _approved_media()
    service, tasks = _service(
        _task(state=ProductionTaskState.PLANNED),
        (media,),
        (_selection(media),),
    )

    result = service.reconcile("PT-20-13-001", now=NOW)

    assert not result.completed
    assert {finding.code for finding in result.assessment.findings} == {
        "task-state-not-completable"
    }
    assert tasks.save_count == 0
