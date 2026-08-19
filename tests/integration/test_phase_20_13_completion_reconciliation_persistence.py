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
)
from vscs.infrastructure.generated_media import (
    JsonGeneratedMediaRepository,
    JsonGeneratedMediaSelectionRepository,
)

NOW = datetime(2026, 8, 19, 17, 30, tzinfo=UTC)
FINGERPRINT = "phase-20-13-persisted-authority"


class MemoryTaskRepository:
    def __init__(self, task: ProductionTask) -> None:
        self.records = {task.task_id: task}

    def get(self, task_id: str) -> ProductionTask | None:
        return self.records.get(task_id)

    def save(self, task: ProductionTask) -> ProductionTask:
        self.records[task.task_id] = task
        return task

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        return tuple(item for item in self.records.values() if item.production_id == production_id)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-13-PERSIST",
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
        expected_outputs=("video/shot",),
        state=ProductionTaskState.READY,
    )


def test_persisted_selected_media_reconciles_authoritative_task_completion(tmp_path) -> None:
    media_root = tmp_path / "media"
    selection_root = tmp_path / "selections"
    media_persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(media_root))
    generated = GeneratedMedia(
        media_id="GM-20-13-PERSIST",
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="XORIX",
            episode_id="EP-001",
            production_task_id="PT-20-13-PERSIST",
            scene_id="SCN-001",
            shot_id="SHT-001",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id="PEX-20-13-PERSIST",
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id="prompt-20-13-persist",
            attributes=(("authority_fingerprint", FINGERPRINT),),
        ),
        file=GeneratedMediaFile(relative_path="generated_media/XORIX/EP-001/media.mp4"),
        technical_metadata=(("technical_validation.status", "passed"),),
    )
    reviewed = media_persistence.governance.submit_for_review(
        generated,
        submitted_by="human:submitter",
        reason="Ready",
        occurred_at=NOW,
    )
    approved = media_persistence.governance.approve(
        reviewed,
        reviewed_by="human:reviewer",
        reason="Accepted",
        occurred_at=NOW,
    )
    media_persistence.register(approved)

    selection_event = GeneratedMediaSelectionEvent(
        previous_media_id=None,
        selected_media_id=approved.media_id,
        selected_revision=approved.revision,
        actor="human:selector",
        reason="Selected for production",
        occurred_at=NOW,
    )
    JsonGeneratedMediaSelectionRepository(selection_root).save(
        GeneratedMediaSelection(
            selection_id="GMS-20-13-PERSIST",
            production_id="XORIX",
            episode_id="EP-001",
            production_task_id="PT-20-13-PERSIST",
            kind=GeneratedMediaKind.VIDEO,
            selected_media_id=approved.media_id,
            selected_revision=approved.revision,
            selected_by=selection_event.actor,
            reason=selection_event.reason,
            selected_at=NOW,
            history=(selection_event,),
        )
    )

    # Recreate both Phase 20 persistence adapters before reconciliation.
    restarted_media = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(media_root))
    restarted_selections = JsonGeneratedMediaSelectionRepository(selection_root)
    tasks = MemoryTaskRepository(_task())
    service = ProductionTaskCompletionReconciliationService(
        lifecycle=ProductionTaskLifecycleService(tasks),
        media=restarted_media,
        selections=restarted_selections,
    )

    result = service.reconcile("PT-20-13-PERSIST", now=NOW)

    assert result.completed
    assert tasks.get("PT-20-13-PERSIST") is not None
    persisted_task = tasks.get("PT-20-13-PERSIST")
    assert persisted_task is not None
    assert persisted_task.state is ProductionTaskState.COMPLETED
    metadata = dict(persisted_task.metadata)
    assert metadata["completion_reconciliation.output.001.media_id"] == approved.media_id
    assert metadata["completion_reconciliation.output.001.selection_id"] == "GMS-20-13-PERSIST"
    assert restarted_media.get(approved.media_id) == approved
    assert restarted_selections.get("GMS-20-13-PERSIST") is not None
