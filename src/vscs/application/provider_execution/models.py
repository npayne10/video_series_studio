"""Provider-neutral execution contracts bridging orchestration to production providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from vscs.application.production_tasks.models import ProductionCapability, ProductionTaskType


class ProviderExecutionPayloadKind(StrEnum):
    """Typed payload families that provider bridges may carry."""

    RENDER = "render"


class ProviderExecutionState(StrEnum):
    """Provider-neutral lifecycle state reported by an execution adapter."""

    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass(frozen=True, slots=True)
class ProviderExecutionContext:
    """Immutable Phase 19 runtime authority attached to one provider execution attempt."""

    execution_id: str
    production_id: str
    task_id: str
    queue_id: str
    entry_id: str
    resource_id: str
    worker_id: str
    lease_id: str
    attempt_number: int
    task_type: ProductionTaskType
    required_capabilities: tuple[ProductionCapability, ...]
    authority_fingerprint: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("execution_id", self.execution_id),
            ("production_id", self.production_id),
            ("task_id", self.task_id),
            ("queue_id", self.queue_id),
            ("entry_id", self.entry_id),
            ("resource_id", self.resource_id),
            ("worker_id", self.worker_id),
            ("lease_id", self.lease_id),
            ("authority_fingerprint", self.authority_fingerprint),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be at least 1")
        if not self.required_capabilities:
            raise ValueError("required_capabilities must not be empty")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("required_capabilities cannot contain duplicates")


@dataclass(frozen=True, slots=True)
class ProviderExecutionRequest:
    """Provider-neutral execution envelope containing governed runtime context."""

    context: ProviderExecutionContext
    payload_kind: ProviderExecutionPayloadKind
    payload: object


@dataclass(frozen=True, slots=True)
class ProviderExecutionHandle:
    """Transient provider job handle returned after submission.

    ``native_handle`` is adapter-owned execution state and is deliberately not production
    authority. Durable execution records are introduced in Phase 20.7.
    """

    execution_id: str
    provider_id: str
    provider_job_id: str
    state: ProviderExecutionState
    submitted_at: datetime
    progress: float = 0.0
    failure_reason: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    native_handle: object | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("execution_id", self.execution_id),
            ("provider_id", self.provider_id),
            ("provider_job_id", self.provider_job_id),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")
        if not 0.0 <= self.progress <= 1.0:
            raise ValueError("progress must be between 0.0 and 1.0")
        keys: set[str] = set()
        for key, value in self.metadata:
            if not key.strip() or not value.strip():
                raise ValueError("metadata keys and values cannot be blank")
            if key in keys:
                raise ValueError("metadata cannot contain duplicate keys")
            keys.add(key)


@dataclass(frozen=True, slots=True)
class ProviderExecutionOutput:
    """Provider output descriptor prior to Generated Media ingestion."""

    output_id: str
    relative_path: str
    media_kind: str
    source_output_id: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.output_id.strip():
            raise ValueError("output_id cannot be blank")
        if not self.media_kind.strip():
            raise ValueError("media_kind cannot be blank")
        normalized = self.relative_path.strip().replace("\\", "/")
        if not normalized or normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("relative_path must remain project-relative")
        object.__setattr__(self, "relative_path", normalized)
        if self.source_output_id is not None and not self.source_output_id.strip():
            raise ValueError("source_output_id cannot be blank when supplied")
