"""Provider-neutral dependency graph integration for ProductionTask authority."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from .lifecycle import ProductionTaskLifecycleService, ProductionTaskTransition
from .models import ProductionTask, ProductionTaskState
from .repository import ProductionTaskRepository


class ProductionTaskGraphError(ValueError):
    """Raised when a ProductionTask dependency graph cannot be evaluated safely."""


class ProductionTaskDependencyDisposition(StrEnum):
    """Current dependency disposition for one non-terminal ProductionTask."""

    READY = "ready"
    WAITING = "waiting"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ProductionTaskGraphRefreshResult:
    """Persisted graph refresh outcome without starting production execution."""

    production_id: str
    tasks: tuple[ProductionTask, ...]
    transitions: tuple[ProductionTaskTransition, ...]


class ProductionTaskGraph:
    """Analyze dependency ordering and readiness for authoritative ProductionTasks."""

    _BLOCKING_STATES = frozenset(
        {
            ProductionTaskState.BLOCKED,
            ProductionTaskState.FAILED,
            ProductionTaskState.CANCELLED,
            ProductionTaskState.SUPERSEDED,
        }
    )

    def __init__(self, tasks: tuple[ProductionTask, ...]) -> None:
        identifiers = [task.task_id for task in tasks]
        if len(set(identifiers)) != len(identifiers):
            raise ProductionTaskGraphError("ProductionTask graph contains duplicate task identities")
        production_ids = {task.production_id for task in tasks}
        if len(production_ids) > 1:
            raise ProductionTaskGraphError(
                "ProductionTask graph cannot mix tasks from different productions"
            )
        self.tasks = tasks
        self._tasks = {task.task_id: task for task in tasks}
        self._validate_dependencies()

    def task(self, task_id: str) -> ProductionTask | None:
        """Return one task by stable identity."""
        return self._tasks.get(task_id)

    def topological_order(self) -> tuple[ProductionTask, ...]:
        """Return tasks in deterministic dependency order."""
        indegree = dict.fromkeys(self._tasks, 0)
        dependants: dict[str, list[str]] = {task_id: [] for task_id in self._tasks}
        for task in self.tasks:
            for dependency in task.dependencies:
                indegree[task.task_id] += 1
                dependants[dependency].append(task.task_id)

        ready = deque(sorted(task_id for task_id, count in indegree.items() if count == 0))
        ordered: list[ProductionTask] = []
        while ready:
            task_id = ready.popleft()
            ordered.append(self._tasks[task_id])
            for dependant in sorted(dependants[task_id]):
                indegree[dependant] -= 1
                if indegree[dependant] == 0:
                    ready.append(dependant)
        if len(ordered) != len(self._tasks):
            raise ProductionTaskGraphError("ProductionTask graph contains a dependency cycle")
        return tuple(ordered)

    def disposition(self, task: ProductionTask) -> ProductionTaskDependencyDisposition:
        """Return whether dependencies make a task ready, waiting, or blocked."""
        if task.task_id not in self._tasks:
            raise ProductionTaskGraphError(
                f"ProductionTask is not part of this graph: {task.task_id}"
            )
        if not task.dependencies:
            return ProductionTaskDependencyDisposition.READY
        dependencies = tuple(self._tasks[dependency] for dependency in task.dependencies)
        if any(dependency.state in self._BLOCKING_STATES for dependency in dependencies):
            return ProductionTaskDependencyDisposition.BLOCKED
        if all(dependency.state is ProductionTaskState.COMPLETED for dependency in dependencies):
            return ProductionTaskDependencyDisposition.READY
        return ProductionTaskDependencyDisposition.WAITING

    def ready_tasks(self) -> tuple[ProductionTask, ...]:
        """Return non-running tasks whose dependencies are fully completed."""
        candidates = {
            ProductionTaskState.PLANNED,
            ProductionTaskState.READY,
            ProductionTaskState.BLOCKED,
        }
        return tuple(
            task
            for task in self.topological_order()
            if task.state in candidates
            and self.disposition(task) is ProductionTaskDependencyDisposition.READY
        )

    def waiting_tasks(self) -> tuple[ProductionTask, ...]:
        """Return planned tasks waiting on healthy, incomplete dependencies."""
        return tuple(
            task
            for task in self.topological_order()
            if task.state is ProductionTaskState.PLANNED
            and self.disposition(task) is ProductionTaskDependencyDisposition.WAITING
        )

    def blocked_tasks(self) -> tuple[ProductionTask, ...]:
        """Return non-terminal tasks blocked by an unavailable dependency chain."""
        blocked_ids: set[str] = set()
        blocked: list[ProductionTask] = []
        candidates = {
            ProductionTaskState.PLANNED,
            ProductionTaskState.READY,
            ProductionTaskState.BLOCKED,
        }
        for task in self.topological_order():
            if task.state not in candidates:
                continue
            dependency_blocked = any(dependency in blocked_ids for dependency in task.dependencies)
            if (
                dependency_blocked
                or self.disposition(task) is ProductionTaskDependencyDisposition.BLOCKED
            ):
                blocked_ids.add(task.task_id)
                blocked.append(task)
        return tuple(blocked)

    def _validate_dependencies(self) -> None:
        for task in self.tasks:
            for dependency in task.dependencies:
                if dependency not in self._tasks:
                    raise ProductionTaskGraphError(
                        f"Unknown dependency {dependency!r} for ProductionTask {task.task_id!r}"
                    )
        self.topological_order()


class ProductionTaskGraphIntegrationService:
    """Persist graph-derived readiness without scheduling or executing ProductionTasks."""

    def __init__(
        self,
        repository: ProductionTaskRepository,
        lifecycle: ProductionTaskLifecycleService,
    ) -> None:
        self.repository = repository
        self.lifecycle = lifecycle

    def graph(self, production_id: str) -> ProductionTaskGraph:
        """Build the authoritative dependency graph for one production."""
        normalized = production_id.strip()
        if not normalized:
            raise ProductionTaskGraphError("production_id cannot be blank")
        return ProductionTaskGraph(self.repository.list_for_production(normalized))

    def refresh(self, production_id: str) -> ProductionTaskGraphRefreshResult:
        """Reconcile PLANNED/READY/BLOCKED states with persisted task dependencies."""
        graph = self.graph(production_id)
        transitions: list[ProductionTaskTransition] = []
        current: dict[str, ProductionTask] = {task.task_id: task for task in graph.tasks}
        blocked_ids = {task.task_id for task in graph.blocked_tasks()}

        for task in graph.topological_order():
            task = current[task.task_id]
            if task.state not in {
                ProductionTaskState.PLANNED,
                ProductionTaskState.READY,
                ProductionTaskState.BLOCKED,
            }:
                continue

            if task.task_id in blocked_ids:
                if task.state is not ProductionTaskState.BLOCKED:
                    updated, transition = self.lifecycle.transition(
                        task.task_id,
                        ProductionTaskState.BLOCKED,
                        reason="ProductionTask dependency graph is blocked",
                    )
                    current[task.task_id] = updated
                    transitions.append(transition)
                continue

            dependencies = tuple(current[dependency] for dependency in task.dependencies)
            dependencies_complete = all(
                dependency.state is ProductionTaskState.COMPLETED for dependency in dependencies
            )
            if dependencies_complete and task.state in {
                ProductionTaskState.PLANNED,
                ProductionTaskState.BLOCKED,
            }:
                updated, transition = self.lifecycle.transition(
                    task.task_id,
                    ProductionTaskState.READY,
                    reason="ProductionTask dependencies are complete",
                )
                current[task.task_id] = updated
                transitions.append(transition)

        tasks = tuple(current[task.task_id] for task in graph.topological_order())
        normalized = production_id.strip()
        return ProductionTaskGraphRefreshResult(
            production_id=normalized,
            tasks=tasks,
            transitions=tuple(transitions),
        )
