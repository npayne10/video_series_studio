"""Provider-neutral ProductionTask lifecycle transitions for Phase 19.6.3."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import ClassVar

from .models import ProductionTask, ProductionTaskState
from .repository import ProductionTaskRepository


class ProductionTaskTransitionError(ValueError):
    """Raised when a ProductionTask lifecycle transition is not permitted."""


@dataclass(frozen=True, slots=True)
class ProductionTaskTransition:
    """Immutable record of one provider-neutral task-state transition."""

    task_id: str
    previous_state: ProductionTaskState
    current_state: ProductionTaskState
    occurred_at: datetime
    reason: str | None = None


class ProductionTaskStageService:
    """Apply the smallest governed lifecycle contract around ProductionTask."""

    _ALLOWED: ClassVar[dict[ProductionTaskState, frozenset[ProductionTaskState]]] = {
        ProductionTaskState.PLANNED: frozenset(
            {
                ProductionTaskState.READY,
                ProductionTaskState.BLOCKED,
                ProductionTaskState.CANCELLED,
                ProductionTaskState.SUPERSEDED,
            }
        ),
        ProductionTaskState.READY: frozenset(
            {
                ProductionTaskState.BLOCKED,
                ProductionTaskState.RUNNING,
                ProductionTaskState.CANCELLED,
                ProductionTaskState.SUPERSEDED,
            }
        ),
        ProductionTaskState.BLOCKED: frozenset(
            {
                ProductionTaskState.READY,
                ProductionTaskState.CANCELLED,
                ProductionTaskState.SUPERSEDED,
            }
        ),
        ProductionTaskState.RUNNING: frozenset(
            {
                ProductionTaskState.COMPLETED,
                ProductionTaskState.FAILED,
                ProductionTaskState.CANCELLED,
            }
        ),
        ProductionTaskState.FAILED: frozenset(
            {
                ProductionTaskState.READY,
                ProductionTaskState.CANCELLED,
                ProductionTaskState.SUPERSEDED,
            }
        ),
        ProductionTaskState.COMPLETED: frozenset(),
        ProductionTaskState.CANCELLED: frozenset(),
        ProductionTaskState.SUPERSEDED: frozenset(),
    }

    def transition(
        self,
        task: ProductionTask,
        target: ProductionTaskState,
        *,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> tuple[ProductionTask, ProductionTaskTransition]:
        """Return a task transitioned to ``target`` and an immutable transition record."""
        if target is task.state:
            raise ProductionTaskTransitionError(
                f"ProductionTask {task.task_id} is already {target.value}"
            )
        allowed = self._ALLOWED[task.state]
        if target not in allowed:
            raise ProductionTaskTransitionError(
                f"ProductionTask {task.task_id} cannot transition "
                f"from {task.state.value} to {target.value}"
            )
        normalized_reason = reason.strip() if reason is not None else None
        if normalized_reason == "":
            normalized_reason = None
        occurred_at = now or datetime.now(UTC)
        updated = replace(task, state=target)
        transition = ProductionTaskTransition(
            task_id=task.task_id,
            previous_state=task.state,
            current_state=target,
            occurred_at=occurred_at,
            reason=normalized_reason,
        )
        return updated, transition


class ProductionTaskLifecycleService:
    """Persist authoritative ProductionTask lifecycle transitions."""

    def __init__(
        self,
        repository: ProductionTaskRepository,
        stages: ProductionTaskStageService | None = None,
    ) -> None:
        self.repository = repository
        self.stages = stages or ProductionTaskStageService()

    def register(self, task: ProductionTask) -> ProductionTask:
        """Persist a compiled task without changing its lifecycle state."""
        return self.repository.save(task)

    def require(self, task_id: str) -> ProductionTask:
        """Return one persisted task or fail with a stable lifecycle error."""
        normalized = task_id.strip()
        if not normalized:
            raise ProductionTaskTransitionError("task_id cannot be blank")
        task = self.repository.get(normalized)
        if task is None:
            raise ProductionTaskTransitionError(f"ProductionTask not found: {normalized}")
        return task

    def transition(
        self,
        task_id: str,
        target: ProductionTaskState,
        *,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> tuple[ProductionTask, ProductionTaskTransition]:
        """Transition and persist one authoritative task."""
        task = self.require(task_id)
        updated, transition = self.stages.transition(
            task,
            target,
            reason=reason,
            now=now,
        )
        return self.repository.save(updated), transition
