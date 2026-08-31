"""Phase 20.18.2 governed ProductionTask supersession regressions."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionResource,
    ProductionResourceCatalog,
    ProductionResourceState,
    ProductionSchedulingUiError,
    ProductionSchedulingUiService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.production_tasks.scheduler import ProductionScheduler


class _TaskRepository:
    def __init__(self, *tasks: ProductionTask) -> None:
        self._tasks = {task.task_id: task for task in tasks}

    def get(self, task_id: str) -> ProductionTask | None:
        return self._tasks.get(task_id)

    def save(self, task: ProductionTask) -> ProductionTask:
        self._tasks[task.task_id] = task
        return task

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        return tuple(
            self._tasks[key]
            for key in sorted(self._tasks)
            if self._tasks[key].production_id == production_id
        )


def _task(
    task_id: str,
    fingerprint: str,
    *,
    state: ProductionTaskState,
    shot_id: str = "EP-001-SCN-001-SHT-001",
) -> ProductionTask:
    return ProductionTask(
        task_id=task_id,
        production_id="VSCS-TSR2",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id=shot_id,
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{shot_id}",
            revision=1,
            fingerprint=fingerprint,
            approved=True,
            approved_by="Neill Payne",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=state,
    )


def _service(repository: _TaskRepository) -> ProductionSchedulingUiService:
    return ProductionSchedulingUiService(
        lambda: repository,
        lambda: None,  # type: ignore[arg-type,return-value]
    )


def test_supersede_obsolete_task_preserves_record_and_removes_it_from_scheduling() -> None:
    obsolete = _task(
        "PT-VIDEO-GENERATION-OLD",
        "old-authority",
        state=ProductionTaskState.READY,
    )
    replacement = _task(
        "PT-VIDEO-GENERATION-NEW",
        "current-authority",
        state=ProductionTaskState.READY,
    )
    repository = _TaskRepository(obsolete, replacement)

    updated = _service(repository).supersede_task(
        obsolete.task_id,
        replacement_task_id=replacement.task_id,
        reason="Replaced by current READY UPD authority",
    )

    assert updated.task_id == obsolete.task_id
    assert updated.state is ProductionTaskState.SUPERSEDED
    assert repository.get(obsolete.task_id) == updated
    assert repository.get(replacement.task_id) == replacement

    schedule = ProductionScheduler().build(
        obsolete.production_id,
        repository.list_for_production(obsolete.production_id),
        ProductionResourceCatalog(
            (
                ProductionResource(
                    resource_id="LOCAL-COMFYUI-LTX23",
                    capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
                    state=ProductionResourceState.AVAILABLE,
                ),
            )
        ),
    )
    assert schedule.scheduled_task_ids == (replacement.task_id,)
    assert obsolete.task_id in schedule.ignored_task_ids


def test_supersession_rejects_replacement_with_same_governed_authority() -> None:
    obsolete = _task(
        "PT-VIDEO-GENERATION-OLD",
        "same-authority",
        state=ProductionTaskState.READY,
    )
    replacement = _task(
        "PT-VIDEO-GENERATION-NEW",
        "same-authority",
        state=ProductionTaskState.PLANNED,
    )
    repository = _TaskRepository(obsolete, replacement)

    with pytest.raises(
        ProductionSchedulingUiError,
        match="different UPD authority",
    ):
        _service(repository).supersede_task(
            obsolete.task_id,
            replacement_task_id=replacement.task_id,
            reason="unsafe",
        )

    assert repository.get(obsolete.task_id) == obsolete


def test_supersession_rejects_replacement_from_another_shot() -> None:
    obsolete = _task(
        "PT-VIDEO-GENERATION-OLD",
        "old-authority",
        state=ProductionTaskState.READY,
    )
    replacement = _task(
        "PT-VIDEO-GENERATION-OTHER-SHOT",
        "other-authority",
        state=ProductionTaskState.PLANNED,
        shot_id="EP-001-SCN-001-SHT-002",
    )
    repository = _TaskRepository(obsolete, replacement)

    with pytest.raises(
        ProductionSchedulingUiError,
        match="same production, Shot, task type and governed UPD identity",
    ):
        _service(repository).supersede_task(
            obsolete.task_id,
            replacement_task_id=replacement.task_id,
            reason="unsafe",
        )


def test_supersession_rejects_terminal_replacement() -> None:
    obsolete = _task(
        "PT-VIDEO-GENERATION-OLD",
        "old-authority",
        state=ProductionTaskState.READY,
    )
    replacement = _task(
        "PT-VIDEO-GENERATION-NEW",
        "current-authority",
        state=ProductionTaskState.SUPERSEDED,
    )
    repository = _TaskRepository(obsolete, replacement)

    with pytest.raises(ProductionSchedulingUiError, match="not active authority"):
        _service(repository).supersede_task(
            obsolete.task_id,
            replacement_task_id=replacement.task_id,
            reason="unsafe",
        )


def test_supersession_rejects_current_task_as_its_own_replacement() -> None:
    current = _task(
        "PT-VIDEO-GENERATION-CURRENT",
        "current-authority",
        state=ProductionTaskState.READY,
    )
    repository = _TaskRepository(current)

    with pytest.raises(ProductionSchedulingUiError, match="cannot supersede itself"):
        _service(repository).supersede_task(
            current.task_id,
            replacement_task_id=current.task_id,
            reason="unsafe",
        )

    assert repository.get(current.task_id) == current
