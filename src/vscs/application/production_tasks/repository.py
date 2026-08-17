"""Persistence contracts for provider-neutral ProductionTask state."""

from __future__ import annotations

from typing import Protocol

from .models import ProductionTask


class ProductionTaskRepositoryError(RuntimeError):
    """Raised when ProductionTask persistence cannot complete safely."""


class ProductionTaskRepository(Protocol):
    """Persistence boundary for authoritative ProductionTask records."""

    def get(self, task_id: str) -> ProductionTask | None:
        """Return one task by stable identity."""
        ...

    def save(self, task: ProductionTask) -> ProductionTask:
        """Create or replace one authoritative task record."""
        ...

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        """Return tasks for one production in deterministic identity order."""
        ...
