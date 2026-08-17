"""Application orchestration for compiled and persisted ProductionTasks."""

from __future__ import annotations

from datetime import datetime

from .compiler import ProductionTaskCompilationContext, ProductionTaskCompilerService
from .lifecycle import (
    ProductionTaskLifecycleService,
    ProductionTaskTransition,
)
from .models import ProductionTask, ProductionTaskState


class ProductionTaskApplicationService:
    """Connect governed task compilation to authoritative task persistence."""

    def __init__(
        self,
        compiler: ProductionTaskCompilerService,
        lifecycle: ProductionTaskLifecycleService,
    ) -> None:
        self.compiler = compiler
        self.lifecycle = lifecycle

    def compile_shot(
        self,
        shot_id: str,
        context: ProductionTaskCompilationContext,
    ) -> tuple[ProductionTask, ...]:
        """Compile current governed authority and persist every resulting task."""
        tasks = self.compiler.compile_shot(shot_id, context)
        return tuple(self.lifecycle.register(task) for task in tasks)

    def transition(
        self,
        task_id: str,
        target: ProductionTaskState,
        *,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> tuple[ProductionTask, ProductionTaskTransition]:
        """Apply and persist one provider-neutral lifecycle transition."""
        return self.lifecycle.transition(task_id, target, reason=reason, now=now)
