"""Authoritative Generated Media domain models for Phase 20.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class GeneratedMediaKind(StrEnum):
    """Provider-neutral media categories owned by VSCS."""

    VIDEO = "video"
    IMAGE = "image"
    IMAGE_SEQUENCE = "image_sequence"
    AUDIO = "audio"
    METADATA = "metadata"
    REPORT = "report"


class GeneratedMediaState(StrEnum):
    """Governance lifecycle for one authoritative Generated Media object."""

    GENERATED = "generated"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    INVALID = "invalid"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class GeneratedMediaScope:
    """Governed production ownership for generated media."""

    production_id: str
    episode_id: str
    production_task_id: str
    scene_id: str | None = None
    shot_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.production_id, "production_id")
        _require_text(self.episode_id, "episode_id")
        _require_text(self.production_task_id, "production_task_id")
        _require_optional_text(self.scene_id, "scene_id")
        _require_optional_text(self.shot_id, "shot_id")


@dataclass(frozen=True, slots=True)
class GeneratedMediaProvenance:
    """Execution provenance describing how one media artifact was produced.

    Provider and workflow details are provenance only. They do not determine Generated
    Media identity, lifecycle authority, approval, or downstream production selection.
    """

    execution_id: str
    provider_id: str
    provider_job_id: str
    render_request_id: str | None = None
    render_output_id: str | None = None
    workflow_id: str | None = None
    queue_entry_id: str | None = None
    worker_id: str | None = None
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.execution_id, "execution_id")
        _require_text(self.provider_id, "provider_id")
        _require_text(self.provider_job_id, "provider_job_id")
        _require_optional_text(self.render_request_id, "render_request_id")
        _require_optional_text(self.render_output_id, "render_output_id")
        _require_optional_text(self.workflow_id, "workflow_id")
        _require_optional_text(self.queue_entry_id, "queue_entry_id")
        _require_optional_text(self.worker_id, "worker_id")
        _require_pairs(self.attributes, "attributes")


@dataclass(frozen=True, slots=True)
class GeneratedMediaFile:
    """Project-relative file identity for one generated artifact."""

    relative_path: str
    checksum_sha256: str | None = None
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        normalized = self.relative_path.strip().replace("\\", "/")
        if not normalized:
            raise ValueError("relative_path cannot be blank")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("relative_path must remain project-relative")
        object.__setattr__(self, "relative_path", normalized)
        if self.checksum_sha256 is not None:
            checksum = self.checksum_sha256.strip().lower()
            if len(checksum) != 64 or any(
                character not in "0123456789abcdef" for character in checksum
            ):
                raise ValueError("checksum_sha256 must be a 64-character hexadecimal SHA-256")
            object.__setattr__(self, "checksum_sha256", checksum)
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")


@dataclass(frozen=True, slots=True)
class GeneratedMediaGovernanceEvent:
    """Immutable audit event for one Generated Media governance transition."""

    from_state: GeneratedMediaState
    to_state: GeneratedMediaState
    actor: str
    reason: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    replacement_media_id: str | None = None

    def __post_init__(self) -> None:
        if self.from_state is self.to_state:
            raise ValueError("governance event must change state")
        _require_text(self.actor, "actor")
        _require_text(self.reason, "reason")
        _require_optional_text(self.replacement_media_id, "replacement_media_id")
        if self.to_state is GeneratedMediaState.SUPERSEDED and self.replacement_media_id is None:
            raise ValueError("superseded governance event requires replacement_media_id")
        if (
            self.to_state is not GeneratedMediaState.SUPERSEDED
            and self.replacement_media_id is not None
        ):
            raise ValueError("replacement_media_id is valid only for supersession")


@dataclass(frozen=True, slots=True)
class GeneratedMedia:
    """Authoritative VSCS record for one provider-generated production artifact."""

    media_id: str
    kind: GeneratedMediaKind
    scope: GeneratedMediaScope
    provenance: GeneratedMediaProvenance
    file: GeneratedMediaFile
    state: GeneratedMediaState = GeneratedMediaState.GENERATED
    revision: int = 1
    technical_metadata: tuple[tuple[str, str], ...] = ()
    governance_history: tuple[GeneratedMediaGovernanceEvent, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require_text(self.media_id, "media_id")
        if self.revision < 1:
            raise ValueError("revision must be at least 1")
        _require_pairs(self.technical_metadata, "technical_metadata")
        if self.governance_history:
            previous_state = GeneratedMediaState.GENERATED
            for event in self.governance_history:
                if event.from_state is not previous_state:
                    raise ValueError("governance_history contains a discontinuous state transition")
                previous_state = event.to_state
            if previous_state is not self.state:
                raise ValueError("Generated Media state must match governance_history")
        elif self.state is not GeneratedMediaState.GENERATED:
            raise ValueError("Generated Media without governance history must start GENERATED")


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")


def _require_optional_text(value: str | None, field_name: str) -> None:
    if value is not None and not value.strip():
        raise ValueError(f"{field_name} cannot be blank when supplied")


def _require_pairs(values: tuple[tuple[str, str], ...], field_name: str) -> None:
    keys: set[str] = set()
    for key, value in values:
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError(f"{field_name} key cannot be blank")
        if not value.strip():
            raise ValueError(f"{field_name} value cannot be blank")
        if normalized_key in keys:
            raise ValueError(f"{field_name} cannot contain duplicate keys")
        keys.add(normalized_key)
