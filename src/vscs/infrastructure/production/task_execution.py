"""ProductionTask-authoritative compatibility wrapper for legacy render execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from vscs.application.production_pipeline import QueueState
from vscs.application.production_tasks import (
    ProductionTask,
    ProductionTaskLegacyBridge,
    ProductionTaskLifecycleService,
    ProductionTaskState,
    ProductionTaskTransition,
    ProductionTaskTransitionError,
)

from .execution import RenderExecutionOutcome, RenderExecutionRequest, RenderExecutionService


@dataclass(frozen=True, slots=True)
class ProductionTaskRenderExecutionOutcome:
    """Authoritative task state plus the unchanged legacy execution outcome."""

    task: ProductionTask
    legacy: RenderExecutionOutcome
    transitions: tuple[ProductionTaskTransition, ...]


class ProductionTaskRenderExecutionService:
    """Run the legacy renderer while ProductionTask owns lifecycle state.

    The wrapped RenderExecutionService remains intact for compatibility. This service
    is the Phase 19.6.3 migration seam: callers that opt into ProductionTask authority
    persist task transitions and receive the legacy queue/pipeline outcome as a
    compatibility projection.
    """

    def __init__(
        self,
        legacy: RenderExecutionService,
        lifecycle: ProductionTaskLifecycleService,
        bridge: ProductionTaskLegacyBridge | None = None,
    ) -> None:
        self.legacy = legacy
        self.lifecycle = lifecycle
        self.bridge = bridge or ProductionTaskLegacyBridge()

    def mark_ready(
        self,
        task_id: str,
        *,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> tuple[ProductionTask, ProductionTaskTransition]:
        """Move a compiled task from planning into executable readiness."""
        return self.lifecycle.transition(
            task_id,
            ProductionTaskState.READY,
            reason=reason or "ProductionTask accepted for execution",
            now=now,
        )

    def execute(
        self,
        task_id: str,
        request: RenderExecutionRequest,
        *,
        now: datetime | None = None,
    ) -> ProductionTaskRenderExecutionOutcome:
        """Execute one READY ProductionTask through the legacy render boundary."""
        current = now or datetime.now(UTC)
        task = self.lifecycle.require(task_id)
        if task.state is not ProductionTaskState.READY:
            raise ProductionTaskTransitionError(
                f"ProductionTask {task.task_id} must be ready before execution; "
                f"current state is {task.state.value}"
            )

        running, started = self.lifecycle.transition(
            task.task_id,
            ProductionTaskState.RUNNING,
            reason="Legacy render execution started",
            now=current,
        )
        transitions: list[ProductionTaskTransition] = [started]

        try:
            legacy_outcome = self.legacy.execute(request, now=current)
        except Exception as exc:
            self.lifecycle.transition(
                running.task_id,
                ProductionTaskState.FAILED,
                reason=f"Legacy render execution could not start: {exc}",
                now=current,
            )
            raise

        terminal_at = (
            legacy_outcome.execution_result.completed_at
            if legacy_outcome.execution_result is not None
            else current
        )
        if (
            legacy_outcome.execution_result is not None
            and legacy_outcome.execution_result.succeeded
        ):
            task, completed = self.lifecycle.transition(
                running.task_id,
                ProductionTaskState.COMPLETED,
                reason="Legacy render execution completed",
                now=terminal_at,
            )
            transitions.append(completed)
        else:
            task, failed = self.lifecycle.transition(
                running.task_id,
                ProductionTaskState.FAILED,
                reason=self._failure_reason(legacy_outcome),
                now=terminal_at,
            )
            transitions.append(failed)
            if legacy_outcome.entry.state is QueueState.RETRYING:
                task, retry_ready = self.lifecycle.transition(
                    task.task_id,
                    ProductionTaskState.READY,
                    reason="Legacy retry policy scheduled another execution attempt",
                    now=terminal_at,
                )
                transitions.append(retry_ready)

        projected_pipeline = self.bridge.reconcile_pipeline(
            legacy_outcome.pipeline,
            task,
            clip_id=legacy_outcome.entry.clip_id,
        )
        projected_outcome = replace(legacy_outcome, pipeline=projected_pipeline)
        return ProductionTaskRenderExecutionOutcome(
            task=task,
            legacy=projected_outcome,
            transitions=tuple(transitions),
        )

    @staticmethod
    def _failure_reason(outcome: RenderExecutionOutcome) -> str:
        if outcome.execution_result is not None and outcome.execution_result.error_message:
            return outcome.execution_result.error_message
        if outcome.events:
            return outcome.events[-1].message
        return "Legacy render execution failed"
