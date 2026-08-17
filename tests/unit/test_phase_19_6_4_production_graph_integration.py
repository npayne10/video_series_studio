"""Focused regression tests for Phase 19.6.4 ProductionGraph integration."""

from dataclasses import replace

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskDependencyDisposition,
    ProductionTaskGraph,
    ProductionTaskGraphError,
    ProductionTaskGraphIntegrationService,
    ProductionTaskLifecycleService,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository


def _task(
    task_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    state: ProductionTaskState = ProductionTaskState.PLANNED,
    production_id: str = "PROD-001",
) -> ProductionTask:
    return ProductionTask(
        task_id=task_id,
        production_id=production_id,
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SHT-001",
            revision=1,
            fingerprint=f"fingerprint-{task_id}",
            approved=True,
            approved_by="tester",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        dependencies=dependencies,
        expected_outputs=("video/shot",),
        state=state,
    )


def test_graph_orders_tasks_deterministically_by_dependencies() -> None:
    graph = ProductionTaskGraph(
        (
            _task("PT-C", dependencies=("PT-B",)),
            _task("PT-A"),
            _task("PT-B", dependencies=("PT-A",)),
        )
    )

    assert tuple(task.task_id for task in graph.topological_order()) == (
        "PT-A",
        "PT-B",
        "PT-C",
    )


def test_graph_rejects_unknown_dependencies() -> None:
    with pytest.raises(ProductionTaskGraphError, match="Unknown dependency"):
        ProductionTaskGraph((_task("PT-A", dependencies=("PT-MISSING",)),))


def test_graph_rejects_cycles() -> None:
    with pytest.raises(ProductionTaskGraphError, match="dependency cycle"):
        ProductionTaskGraph(
            (
                _task("PT-A", dependencies=("PT-B",)),
                _task("PT-B", dependencies=("PT-A",)),
            )
        )


def test_graph_rejects_duplicate_task_ids_and_mixed_productions() -> None:
    with pytest.raises(ProductionTaskGraphError, match="duplicate task identities"):
        ProductionTaskGraph((_task("PT-A"), _task("PT-A")))

    with pytest.raises(ProductionTaskGraphError, match="different productions"):
        ProductionTaskGraph(
            (
                _task("PT-A", production_id="PROD-001"),
                _task("PT-B", production_id="PROD-002"),
            )
        )


def test_graph_distinguishes_ready_waiting_and_blocked_dependencies() -> None:
    completed = _task("PT-A", state=ProductionTaskState.COMPLETED)
    waiting = _task("PT-B")
    ready_child = _task("PT-C", dependencies=("PT-A",))
    waiting_child = _task("PT-D", dependencies=("PT-B",))
    failed = _task("PT-E", state=ProductionTaskState.FAILED)
    blocked_child = _task("PT-F", dependencies=("PT-E",))
    graph = ProductionTaskGraph(
        (completed, waiting, ready_child, waiting_child, failed, blocked_child)
    )

    assert graph.disposition(ready_child) is ProductionTaskDependencyDisposition.READY
    assert graph.disposition(waiting_child) is ProductionTaskDependencyDisposition.WAITING
    assert graph.disposition(blocked_child) is ProductionTaskDependencyDisposition.BLOCKED
    assert tuple(task.task_id for task in graph.ready_tasks()) == ("PT-B", "PT-C")
    assert tuple(task.task_id for task in graph.waiting_tasks()) == ("PT-D",)
    assert tuple(task.task_id for task in graph.blocked_tasks()) == ("PT-F",)


def test_blocked_dependency_state_propagates_through_descendants() -> None:
    graph = ProductionTaskGraph(
        (
            _task("PT-A", state=ProductionTaskState.CANCELLED),
            _task("PT-B", dependencies=("PT-A",)),
            _task("PT-C", dependencies=("PT-B",)),
        )
    )

    assert tuple(task.task_id for task in graph.blocked_tasks()) == ("PT-B", "PT-C")


def test_graph_refresh_persists_readiness_without_starting_execution(tmp_path) -> None:
    repository = JsonProductionTaskRepository(tmp_path / "production_tasks")
    lifecycle = ProductionTaskLifecycleService(repository)
    service = ProductionTaskGraphIntegrationService(repository, lifecycle)
    root = _task("PT-A")
    child = _task("PT-B", dependencies=("PT-A",))
    repository.save(root)
    repository.save(child)

    first = service.refresh("PROD-001")

    assert repository.get("PT-A").state is ProductionTaskState.READY
    assert repository.get("PT-B").state is ProductionTaskState.PLANNED
    assert tuple(
        (transition.task_id, transition.current_state) for transition in first.transitions
    ) == (("PT-A", ProductionTaskState.READY),)
    assert all(task.state is not ProductionTaskState.RUNNING for task in first.tasks)

    repository.save(replace(repository.get("PT-A"), state=ProductionTaskState.COMPLETED))
    second = service.refresh("PROD-001")

    assert repository.get("PT-B").state is ProductionTaskState.READY
    assert tuple(
        (transition.task_id, transition.current_state) for transition in second.transitions
    ) == (("PT-B", ProductionTaskState.READY),)


def test_graph_refresh_blocks_failed_dependency_chain_and_is_production_scoped(tmp_path) -> None:
    repository = JsonProductionTaskRepository(tmp_path / "production_tasks")
    lifecycle = ProductionTaskLifecycleService(repository)
    service = ProductionTaskGraphIntegrationService(repository, lifecycle)
    repository.save(_task("PT-A", state=ProductionTaskState.FAILED))
    repository.save(_task("PT-B", dependencies=("PT-A",)))
    repository.save(_task("PT-C", dependencies=("PT-B",)))
    repository.save(_task("OTHER-A", production_id="PROD-002"))

    result = service.refresh("PROD-001")

    assert tuple(task.task_id for task in result.tasks) == ("PT-A", "PT-B", "PT-C")
    assert repository.get("PT-B").state is ProductionTaskState.BLOCKED
    assert repository.get("PT-C").state is ProductionTaskState.BLOCKED
    assert repository.get("OTHER-A").state is ProductionTaskState.PLANNED
