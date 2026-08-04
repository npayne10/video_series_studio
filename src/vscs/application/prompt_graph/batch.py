"""Deterministic synchronous batch prompt compilation orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from .builder import PromptGraphBuilder
from .compiler import PromptGraphCompiler
from .context import PromptGraphBuildContext
from .renderer_profiles import (
    ProfiledPromptPackage,
    RendererPromptCompiler,
    RendererPromptProfileRegistry,
)
from .validation import PromptGraphResourceInventory


class BatchCompilationStatus(StrEnum):
    """Lifecycle state of one batch compilation job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchCompilationItemStatus(StrEnum):
    """Outcome state of one item within a compilation batch."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class BatchCompilationItem:
    """One deterministic graph-to-profile compilation unit."""

    item_id: str
    context: PromptGraphBuildContext
    inventory: PromptGraphResourceInventory = field(
        default_factory=PromptGraphResourceInventory
    )
    sequence: int = 0
    renderer_profile_id: str | None = None
    require_production_ready: bool = True

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("item_id is required")
        if self.sequence < 0:
            raise ValueError("sequence cannot be negative")


@dataclass(frozen=True, slots=True)
class BatchCompilationRequest:
    """Immutable request to compile one or more prompt graph items."""

    batch_id: str
    items: tuple[BatchCompilationItem, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.batch_id.strip():
            raise ValueError("batch_id is required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if not self.items:
            raise ValueError("batch compilation requires at least one item")
        item_ids = tuple(item.item_id for item in self.items)
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("batch item IDs must be unique")

    @classmethod
    def create(
        cls,
        batch_id: str,
        items: tuple[BatchCompilationItem, ...],
        *,
        created_at: datetime | None = None,
    ) -> BatchCompilationRequest:
        return cls(batch_id, items, created_at or datetime.now(UTC))

    @property
    def ordered_items(self) -> tuple[BatchCompilationItem, ...]:
        return tuple(
            sorted(
                self.items,
                key=lambda item: (
                    item.sequence,
                    item.context.container_id,
                    item.context.scene_id,
                    item.context.shot_id,
                    item.context.clip_id or "",
                    item.item_id,
                ),
            )
        )


@dataclass(frozen=True, slots=True)
class BatchCompilationItemResult:
    """Result of one isolated batch item compilation."""

    item_id: str
    shot_id: str
    status: BatchCompilationItemStatus
    package: ProfiledPromptPackage | None = None
    error_type: str = ""
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class BatchCompilationProgress:
    """Immutable progress snapshot emitted during synchronous execution."""

    batch_id: str
    status: BatchCompilationStatus
    total_items: int
    completed_items: int
    failed_items: int
    cancelled_items: int
    remaining_items: int
    current_item_id: str | None = None

    @property
    def processed_items(self) -> int:
        return self.completed_items + self.failed_items + self.cancelled_items

    @property
    def percentage(self) -> int:
        if self.total_items == 0:
            return 100
        return round(self.processed_items * 100 / self.total_items)


@dataclass(frozen=True, slots=True)
class BatchCompilationJob:
    """Final immutable outcome of one batch compilation request."""

    request: BatchCompilationRequest
    status: BatchCompilationStatus
    started_at: datetime
    finished_at: datetime
    results: tuple[BatchCompilationItemResult, ...]

    @property
    def completed_results(self) -> tuple[BatchCompilationItemResult, ...]:
        return self._results(BatchCompilationItemStatus.COMPLETED)

    @property
    def failed_results(self) -> tuple[BatchCompilationItemResult, ...]:
        return self._results(BatchCompilationItemStatus.FAILED)

    @property
    def cancelled_results(self) -> tuple[BatchCompilationItemResult, ...]:
        return self._results(BatchCompilationItemStatus.CANCELLED)

    @property
    def packages(self) -> tuple[ProfiledPromptPackage, ...]:
        return tuple(
            result.package
            for result in self.completed_results
            if result.package is not None
        )

    @property
    def progress(self) -> BatchCompilationProgress:
        completed = len(self.completed_results)
        failed = len(self.failed_results)
        cancelled = len(self.cancelled_results)
        total = len(self.request.items)
        return BatchCompilationProgress(
            self.request.batch_id,
            self.status,
            total,
            completed,
            failed,
            cancelled,
            total - completed - failed - cancelled,
        )

    def _results(
        self,
        status: BatchCompilationItemStatus,
    ) -> tuple[BatchCompilationItemResult, ...]:
        return tuple(result for result in self.results if result.status is status)


ProgressCallback = Callable[[BatchCompilationProgress], None]
CancellationPredicate = Callable[[], bool]


@dataclass(slots=True)
class BatchPromptCompilationService:
    """Compile multiple shots through the approved prompt pipeline."""

    builder: PromptGraphBuilder
    graph_compiler: PromptGraphCompiler
    profile_registry: RendererPromptProfileRegistry
    renderer_compiler: RendererPromptCompiler

    def compile(
        self,
        request: BatchCompilationRequest,
        *,
        on_progress: ProgressCallback | None = None,
        should_cancel: CancellationPredicate | None = None,
    ) -> BatchCompilationJob:
        started_at = datetime.now(UTC)
        total = len(request.items)
        completed = 0
        failed = 0
        cancelled = 0
        results: list[BatchCompilationItemResult] = []
        self._notify(
            on_progress,
            self._progress(request.batch_id, total, completed, failed, cancelled),
        )
        ordered = request.ordered_items
        for index, item in enumerate(ordered):
            if should_cancel is not None and should_cancel():
                remaining = ordered[index:]
                results.extend(
                    BatchCompilationItemResult(
                        pending.item_id,
                        pending.context.shot_id,
                        BatchCompilationItemStatus.CANCELLED,
                    )
                    for pending in remaining
                )
                cancelled += len(remaining)
                break
            self._notify(
                on_progress,
                self._progress(
                    request.batch_id,
                    total,
                    completed,
                    failed,
                    cancelled,
                    item.item_id,
                ),
            )
            try:
                build = self.builder.build(item.context)
                package = self.graph_compiler.compile(
                    build.graph,
                    item.inventory,
                    require_production_ready=item.require_production_ready,
                )
                profile = (
                    self.profile_registry.require(item.renderer_profile_id)
                    if item.renderer_profile_id
                    else self.profile_registry.resolve(
                        item.context.renderer,
                        item.context.quality_level,
                    )
                )
                profiled = self.renderer_compiler.compile(package, profile)
                results.append(
                    BatchCompilationItemResult(
                        item.item_id,
                        item.context.shot_id,
                        BatchCompilationItemStatus.COMPLETED,
                        package=profiled,
                    )
                )
                completed += 1
            except Exception as exc:
                results.append(
                    BatchCompilationItemResult(
                        item.item_id,
                        item.context.shot_id,
                        BatchCompilationItemStatus.FAILED,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                failed += 1
            self._notify(
                on_progress,
                self._progress(
                    request.batch_id,
                    total,
                    completed,
                    failed,
                    cancelled,
                    item.item_id,
                ),
            )
        status = self._final_status(completed, failed, cancelled)
        job = BatchCompilationJob(
            request=request,
            status=status,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            results=tuple(results),
        )
        self._notify(on_progress, job.progress)
        return job

    @staticmethod
    def _progress(
        batch_id: str,
        total: int,
        completed: int,
        failed: int,
        cancelled: int,
        current_item_id: str | None = None,
    ) -> BatchCompilationProgress:
        return BatchCompilationProgress(
            batch_id,
            BatchCompilationStatus.RUNNING,
            total,
            completed,
            failed,
            cancelled,
            total - completed - failed - cancelled,
            current_item_id,
        )

    @staticmethod
    def _final_status(
        completed: int,
        failed: int,
        cancelled: int,
    ) -> BatchCompilationStatus:
        if cancelled:
            return BatchCompilationStatus.CANCELLED
        if failed == 0:
            return BatchCompilationStatus.COMPLETED
        if completed == 0:
            return BatchCompilationStatus.FAILED
        return BatchCompilationStatus.COMPLETED_WITH_FAILURES

    @staticmethod
    def _notify(
        callback: ProgressCallback | None,
        progress: BatchCompilationProgress,
    ) -> None:
        if callback is not None:
            callback(progress)
