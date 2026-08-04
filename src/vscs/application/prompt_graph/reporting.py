"""Structured and human-readable batch compilation reporting."""

from __future__ import annotations

from dataclasses import dataclass

from .batch import BatchCompilationJob
from .history import BatchCompilationHistory, BatchHistoryRecord
from .statistics import BatchStatistics, BatchStatisticsService


@dataclass(frozen=True, slots=True)
class BatchCompilationReport:
    """Immutable operational report for one terminal batch."""

    record: BatchHistoryRecord
    statistics: BatchStatistics
    failures: tuple[tuple[str, str, str], ...]

    @property
    def success_percentage(self) -> float:
        if self.record.total_items == 0:
            return 100.0
        successful = self.record.completed_items + self.record.skipped_items
        return successful * 100.0 / self.record.total_items

    def to_text(self) -> str:
        renderer = ", ".join(self.record.renderer_ids) or "none"
        quality = ", ".join(self.record.quality_levels) or "none"
        profiles = ", ".join(self.record.renderer_profile_ids) or "none"
        workflows = ", ".join(self.record.workflow_ids) or "none"
        lines = [
            f"Batch Compilation Report: {self.record.batch_id}",
            f"Status: {self.record.status.value}",
            f"Renderer: {renderer}",
            f"Quality: {quality}",
            f"Duration: {self.record.duration_seconds:.3f} seconds",
            f"Completed: {self.record.completed_items}",
            f"Skipped: {self.record.skipped_items}",
            f"Failed: {self.record.failed_items}",
            f"Cancelled: {self.record.cancelled_items}",
            f"Success: {self.success_percentage:.1f}%",
            f"Throughput: {self.record.throughput_per_minute:.2f} items/minute",
            f"Renderer profiles: {profiles}",
            f"Workflows: {workflows}",
            f"Result checksum: {self.record.result_checksum}",
        ]
        if self.failures:
            lines.append("Failures:")
            lines.extend(
                f"- {item_id}: {error_type}: {message}"
                for item_id, error_type, message in self.failures
            )
        return "\n".join(lines)

    def to_markdown(self) -> str:
        renderer = ", ".join(self.record.renderer_ids) or "none"
        quality = ", ".join(self.record.quality_levels) or "none"
        lines = [
            f"# Batch Compilation Report — {self.record.batch_id}",
            "",
            "## Summary",
            "",
            f"- **Status:** {self.record.status.value}",
            f"- **Renderer:** {renderer}",
            f"- **Quality:** {quality}",
            f"- **Duration:** {self.record.duration_seconds:.3f} seconds",
            "",
            "## Production",
            "",
            f"- **Completed:** {self.record.completed_items}",
            f"- **Skipped:** {self.record.skipped_items}",
            f"- **Failed:** {self.record.failed_items}",
            f"- **Cancelled:** {self.record.cancelled_items}",
            f"- **Success:** {self.success_percentage:.1f}%",
            "",
            "## Timing",
            "",
            f"- **Throughput:** {self.record.throughput_per_minute:.2f} items/minute",
            "",
            "## Provenance",
            "",
            f"- **Renderer profiles:** {', '.join(self.record.renderer_profile_ids) or 'none'}",
            f"- **Workflows:** {', '.join(self.record.workflow_ids) or 'none'}",
            f"- **Graph versions:** {', '.join(self.record.graph_versions) or 'none'}",
            f"- **Result checksum:** `{self.record.result_checksum}`",
        ]
        if self.failures:
            lines.extend(("", "## Failures", ""))
            lines.extend(
                f"- `{item_id}` — **{error_type}:** {message}"
                for item_id, error_type, message in self.failures
            )
        return "\n".join(lines)


@dataclass(slots=True)
class BatchReportingService:
    """Create reports and aggregate statistics for terminal batch jobs."""

    history: BatchCompilationHistory
    statistics_service: BatchStatisticsService

    def record(self, job: BatchCompilationJob) -> BatchCompilationReport:
        record = self.history.record(job)
        failures = tuple(
            (result.item_id, result.error_type, result.error_message)
            for result in job.failed_results
        )
        return BatchCompilationReport(
            record=record,
            statistics=self.statistics_service.calculate(),
            failures=failures,
        )

    def for_batch(self, batch_id: str) -> BatchCompilationReport | None:
        record = self.history.by_batch(batch_id)
        if record is None:
            return None
        return BatchCompilationReport(
            record=record,
            statistics=self.statistics_service.calculate(),
            failures=(),
        )
