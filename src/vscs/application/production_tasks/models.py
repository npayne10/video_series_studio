"""Provider-neutral ProductionTask domain models for VSCS vNext."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum


class ProductionTaskType(StrEnum):
    """Production work categories independent of any execution provider."""

    REFERENCE_GENERATION = "reference_generation"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    VOICE_GENERATION = "voice_generation"
    LIP_SYNC = "lip_sync"
    MUSIC_GENERATION = "music_generation"
    AUDIO_GENERATION = "audio_generation"
    POST_PROCESSING = "post_processing"
    QUALITY_CONTROL = "quality_control"
    REPAIR = "repair"
    SCENE_ASSEMBLY = "scene_assembly"
    EPISODE_ASSEMBLY = "episode_assembly"
    MASTERING = "mastering"
    DELIVERY = "delivery"


class ProductionTaskState(StrEnum):
    """Provider-neutral lifecycle state for one production task."""

    PLANNED = "planned"
    READY = "ready"
    BLOCKED = "blocked"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class ProductionTaskPriority(IntEnum):
    """Scheduling priority for one production task."""

    LOW = 10
    NORMAL = 20
    HIGH = 30
    URGENT = 40


class ProductionCapability(StrEnum):
    """Provider-neutral capabilities that a production resource may advertise."""

    REFERENCE_GENERATION = "reference_generation"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    VOICE_GENERATION = "voice_generation"
    LIP_SYNC = "lip_sync"
    MUSIC_GENERATION = "music_generation"
    AUDIO_GENERATION = "audio_generation"
    POST_PROCESSING = "post_processing"
    QUALITY_CONTROL = "quality_control"
    REPAIR = "repair"
    ASSEMBLY = "assembly"
    MASTERING = "mastering"
    DELIVERY = "delivery"


class ProductionAuthorityType(StrEnum):
    """Governed authority kinds allowed to originate production work."""

    UNIVERSAL_PRODUCTION_DESCRIPTION = "universal_production_description"


@dataclass(frozen=True, slots=True)
class ProductionTaskAuthority:
    """Immutable reference to the governed authority that created a task."""

    authority_type: ProductionAuthorityType
    authority_id: str
    revision: int
    fingerprint: str
    approved: bool
    approved_by: str | None

    def __post_init__(self) -> None:
        _require_text(self.authority_id, "authority_id")
        _require_text(self.fingerprint, "fingerprint")
        if self.revision < 1:
            raise ValueError("revision must be at least 1")
        if self.approved and not _has_text(self.approved_by):
            raise ValueError("approved authority requires approved_by")


@dataclass(frozen=True, slots=True)
class ProductionTaskAttemptPolicy:
    """Provider-neutral retry limits associated with a production task."""

    maximum_attempts: int = 3
    retry_delay_seconds: int = 0

    def __post_init__(self) -> None:
        if self.maximum_attempts < 1:
            raise ValueError("maximum_attempts must be at least 1")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")


@dataclass(frozen=True, slots=True)
class ProductionTask:
    """One immutable unit of provider-neutral production work."""

    task_id: str
    production_id: str
    episode_id: str
    task_type: ProductionTaskType
    authority: ProductionTaskAuthority
    capabilities: tuple[ProductionCapability, ...]
    expected_outputs: tuple[str, ...]
    scene_id: str | None = None
    shot_id: str | None = None
    dependencies: tuple[str, ...] = ()
    required_inputs: tuple[str, ...] = ()
    priority: ProductionTaskPriority = ProductionTaskPriority.NORMAL
    state: ProductionTaskState = ProductionTaskState.PLANNED
    attempt_policy: ProductionTaskAttemptPolicy = field(default_factory=ProductionTaskAttemptPolicy)
    provenance: tuple[tuple[str, str], ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require_text(self.task_id, "task_id")
        _require_text(self.production_id, "production_id")
        _require_text(self.episode_id, "episode_id")
        _require_unique_nonblank(self.dependencies, "dependencies")
        _require_unique_nonblank(self.required_inputs, "required_inputs")
        _require_unique_nonblank(self.expected_outputs, "expected_outputs")
        if not self.capabilities:
            raise ValueError("capabilities must contain at least one provider-neutral capability")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities cannot contain duplicates")
        if not self.expected_outputs:
            raise ValueError("expected_outputs must contain at least one output contract")
        if self.task_id in self.dependencies:
            raise ValueError("a ProductionTask cannot depend on itself")
        _require_pairs(self.provenance, "provenance")
        _require_pairs(self.metadata, "metadata")


def _has_text(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")


def _require_unique_nonblank(values: tuple[str, ...], field_name: str) -> None:
    for value in values:
        _require_text(value, field_name)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} cannot contain duplicates")


def _require_pairs(values: tuple[tuple[str, str], ...], field_name: str) -> None:
    keys: set[str] = set()
    for key, value in values:
        _require_text(key, f"{field_name} key")
        _require_text(value, f"{field_name} value")
        if key in keys:
            raise ValueError(f"{field_name} cannot contain duplicate keys")
        keys.add(key)
