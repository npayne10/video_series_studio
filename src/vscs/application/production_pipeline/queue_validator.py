"""Validation for production render queues."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .queue_models import QueueState, RenderQueue


class QueueValidationSeverity(StrEnum):
    """Severity assigned to one queue validation issue."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class QueueValidationIssue:
    """One machine-readable queue validation finding."""

    severity: QueueValidationSeverity
    code: str
    message: str
    entry_id: str | None = None


@dataclass(frozen=True, slots=True)
class QueueValidationResult:
    """Complete render queue validation result."""

    issues: tuple[QueueValidationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        """Return whether the queue has no error-level findings."""
        return not any(
            issue.severity is QueueValidationSeverity.ERROR for issue in self.issues
        )


class RenderQueueValidator:
    """Validate queue identity, dependencies, attempts, and runtime state."""

    def validate(self, queue: RenderQueue) -> QueueValidationResult:
        """Validate one render queue."""
        issues: list[QueueValidationIssue] = []
        if not queue.queue_id.strip():
            self._error(issues, "QUEUE_ID_MISSING", "Queue ID must not be empty.")
        if not queue.pipeline_id.strip():
            self._error(issues, "PIPELINE_ID_MISSING", "Pipeline ID must not be empty.")
        if not queue.schema_version.strip():
            self._error(issues, "SCHEMA_VERSION_MISSING", "Schema version must not be empty.")

        entry_ids = [entry.entry_id for entry in queue.entries]
        known = set(entry_ids)
        if len(known) != len(entry_ids):
            self._error(issues, "DUPLICATE_ENTRY_ID", "Queue entry IDs must be unique.")

        for entry in queue.entries:
            if not entry.entry_id.strip():
                self._error(
                    issues,
                    "ENTRY_ID_MISSING",
                    "Queue entry ID must not be empty.",
                    entry.entry_id,
                )
            if entry.maximum_attempts < 1:
                self._error(
                    issues,
                    "INVALID_MAXIMUM_ATTEMPTS",
                    "Maximum attempts must be at least one.",
                    entry.entry_id,
                )
            if entry.entry_id in entry.dependencies:
                self._error(
                    issues,
                    "SELF_DEPENDENCY",
                    "Queue entries may not depend on themselves.",
                    entry.entry_id,
                )
            if len(set(entry.dependencies)) != len(entry.dependencies):
                self._error(
                    issues,
                    "DUPLICATE_DEPENDENCY",
                    "Queue entry dependencies must be unique.",
                    entry.entry_id,
                )
            for dependency in entry.dependencies:
                if dependency not in known:
                    self._error(
                        issues,
                        "UNKNOWN_DEPENDENCY",
                        f"Unknown queue dependency: {dependency}",
                        entry.entry_id,
                    )
            if entry.attempt_count > entry.maximum_attempts:
                self._error(
                    issues,
                    "ATTEMPT_LIMIT_EXCEEDED",
                    "Attempt count exceeds maximum attempts.",
                    entry.entry_id,
                )
            numbers = tuple(attempt.attempt_number for attempt in entry.attempts)
            if numbers != tuple(range(1, len(numbers) + 1)):
                self._error(
                    issues,
                    "INVALID_ATTEMPT_SEQUENCE",
                    "Attempt numbers must be consecutive starting at one.",
                    entry.entry_id,
                )
            if entry.state in {QueueState.CLAIMED, QueueState.RUNNING}:
                if entry.claimed_by is None:
                    self._error(
                        issues,
                        "WORKER_CLAIM_MISSING",
                        "Claimed and running entries require a worker ID.",
                        entry.entry_id,
                    )
            elif entry.claimed_by is not None:
                self._error(
                    issues,
                    "STALE_WORKER_CLAIM",
                    "Only claimed and running entries may retain a worker ID.",
                    entry.entry_id,
                )

        self._validate_cycles(queue, issues)
        return QueueValidationResult(tuple(issues))

    @staticmethod
    def _validate_cycles(
        queue: RenderQueue,
        issues: list[QueueValidationIssue],
    ) -> None:
        dependencies = {entry.entry_id: entry.dependencies for entry in queue.entries}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(entry_id: str) -> bool:
            if entry_id in visiting:
                return True
            if entry_id in visited:
                return False
            visiting.add(entry_id)
            for dependency in dependencies.get(entry_id, ()):
                if dependency in dependencies and visit(dependency):
                    return True
            visiting.remove(entry_id)
            visited.add(entry_id)
            return False

        if any(visit(entry_id) for entry_id in dependencies if entry_id not in visited):
            RenderQueueValidator._error(
                issues,
                "DEPENDENCY_CYCLE",
                "Render queue dependencies must not contain cycles.",
            )

    @staticmethod
    def _error(
        issues: list[QueueValidationIssue],
        code: str,
        message: str,
        entry_id: str | None = None,
    ) -> None:
        issues.append(
            QueueValidationIssue(
                severity=QueueValidationSeverity.ERROR,
                code=code,
                message=message,
                entry_id=entry_id,
            )
        )
