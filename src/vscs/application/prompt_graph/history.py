"""Immutable in-memory history for terminal batch compilation jobs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from vscs.application.rendering import QualityLevel, RendererKind

from .batch import BatchCompilationJob, BatchCompilationStatus


@dataclass(frozen=True, slots=True)
class BatchHistoryRecord:
    """Operational and provenance summary of one completed batch job."""

    batch_id: str
    status: BatchCompilationStatus
    started_at: object
    finished_at: object
    duration_seconds: float
    total_items: int
    completed_items: int
    skipped_items: int
    failed_items: int
    cancelled_items: int
    renderer_ids: tuple[str, ...]
    quality_levels: tuple[str, ...]
    renderer_profile_ids: tuple[str, ...]
    workflow_ids: tuple[str, ...]
    graph_versions: tuple[str, ...]
    result_checksum: str

    @classmethod
    def from_job(cls, job: BatchCompilationJob) -> BatchHistoryRecord:
        packages = job.packages
        checksum_input = "\n".join(
            sorted(
                f"{result.item_id}:{result.status.value}:"
                f"{result.package.source.provenance.graph_checksum if result.package else ''}"
                for result in job.results
            )
        )
        contexts = tuple(item.context for item in job.request.items)
        return cls(
            batch_id=job.request.batch_id,
            status=job.status,
            started_at=job.started_at,
            finished_at=job.finished_at,
            duration_seconds=max((job.finished_at - job.started_at).total_seconds(), 0.0),
            total_items=len(job.request.items),
            completed_items=len(job.completed_results),
            skipped_items=len(job.skipped_results),
            failed_items=len(job.failed_results),
            cancelled_items=len(job.cancelled_results),
            renderer_ids=tuple(sorted({context.renderer.value for context in contexts})),
            quality_levels=tuple(
                sorted({context.quality_level.value for context in contexts})
            ),
            renderer_profile_ids=tuple(
                sorted({package.profile.profile_id for package in packages})
            ),
            workflow_ids=tuple(sorted({context.workflow_id for context in contexts})),
            graph_versions=tuple(
                sorted({package.source.provenance.graph_version for package in packages})
            ),
            result_checksum=hashlib.sha256(checksum_input.encode("utf-8")).hexdigest(),
        )

    @property
    def processed_items(self) -> int:
        return (
            self.completed_items
            + self.skipped_items
            + self.failed_items
            + self.cancelled_items
        )

    @property
    def throughput_per_minute(self) -> float:
        if self.duration_seconds <= 0.0:
            return 0.0
        return self.processed_items * 60.0 / self.duration_seconds


@dataclass(slots=True)
class BatchCompilationHistory:
    """Store terminal batch records in stable completion order."""

    _records: dict[str, BatchHistoryRecord] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def record(self, job: BatchCompilationJob) -> BatchHistoryRecord:
        record = BatchHistoryRecord.from_job(job)
        if record.batch_id not in self._records:
            self._order.append(record.batch_id)
        self._records[record.batch_id] = record
        return record

    def by_batch(self, batch_id: str) -> BatchHistoryRecord | None:
        return self._records.get(batch_id)

    def latest(self) -> BatchHistoryRecord | None:
        return self._records[self._order[-1]] if self._order else None

    def last(self, count: int) -> tuple[BatchHistoryRecord, ...]:
        if count < 0:
            raise ValueError("count cannot be negative")
        return tuple(self._records[batch_id] for batch_id in self._order[-count:])

    def all(self) -> tuple[BatchHistoryRecord, ...]:
        return tuple(self._records[batch_id] for batch_id in self._order)

    def completed(self) -> tuple[BatchHistoryRecord, ...]:
        statuses = {
            BatchCompilationStatus.COMPLETED,
            BatchCompilationStatus.COMPLETED_WITH_FAILURES,
        }
        return tuple(record for record in self.all() if record.status in statuses)

    def failed(self) -> tuple[BatchHistoryRecord, ...]:
        return tuple(
            record
            for record in self.all()
            if record.status is BatchCompilationStatus.FAILED
        )
