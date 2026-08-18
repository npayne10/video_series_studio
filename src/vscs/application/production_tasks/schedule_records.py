"""Durable ProductionSchedule revisions and explicit human review governance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from .scheduler import ProductionSchedule


class ProductionSchedulePersistenceError(RuntimeError):
    """Raised when durable schedule revision handling cannot complete safely."""


class ProductionScheduleReviewError(RuntimeError):
    """Raised when schedule review governance cannot complete safely."""


class ProductionScheduleReviewDecision(StrEnum):
    """Explicit human decisions available for one schedule revision."""

    APPROVED = "approved"
    REJECTED = "rejected"


class ProductionScheduleReviewState(StrEnum):
    """Effective review state for one persisted schedule revision."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class ProductionScheduleSnapshot:
    """One immutable, fingerprinted schedule revision."""

    schedule_id: str
    production_id: str
    revision: int
    fingerprint: str
    schedule: ProductionSchedule
    created_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.schedule_id, "schedule_id")
        _require_text(self.production_id, "production_id")
        _require_text(self.fingerprint, "fingerprint")
        if self.revision < 1:
            raise ValueError("revision must be at least 1")
        if self.schedule.production_id != self.production_id:
            raise ValueError("schedule production_id must match snapshot production_id")
        if self.fingerprint != production_schedule_fingerprint(self.schedule):
            raise ValueError("schedule fingerprint does not match schedule content")


@dataclass(frozen=True, slots=True)
class ProductionScheduleReviewRecord:
    """One immutable human review decision tied to an exact schedule fingerprint."""

    schedule_id: str
    production_id: str
    revision: int
    fingerprint: str
    decision: ProductionScheduleReviewDecision
    reviewed_by: str
    notes: str
    reviewed_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.schedule_id, "schedule_id")
        _require_text(self.production_id, "production_id")
        _require_text(self.fingerprint, "fingerprint")
        _require_text(self.reviewed_by, "reviewed_by")
        _require_text(self.notes, "notes")
        if self.revision < 1:
            raise ValueError("revision must be at least 1")


@dataclass(frozen=True, slots=True)
class ProductionScheduleReviewView:
    """Current review interpretation for one persisted schedule revision."""

    snapshot: ProductionScheduleSnapshot
    review: ProductionScheduleReviewRecord | None
    state: ProductionScheduleReviewState
    current: bool
    can_review: bool


class ProductionScheduleSource(Protocol):
    """Provider-neutral source capable of producing a schedule for one production."""

    def schedule(self, production_id: str) -> ProductionSchedule:
        """Build a schedule without starting execution."""
        ...


class ProductionScheduleRepository(Protocol):
    """Persistence boundary for immutable schedule revisions and review decisions."""

    def save_snapshot(self, snapshot: ProductionScheduleSnapshot) -> ProductionScheduleSnapshot:
        """Persist a new immutable schedule revision."""
        ...

    def get_snapshot(self, schedule_id: str, revision: int) -> ProductionScheduleSnapshot | None:
        """Return one exact schedule revision."""
        ...

    def history_for_production(
        self,
        production_id: str,
    ) -> tuple[ProductionScheduleSnapshot, ...]:
        """Return schedule revisions for one production in revision order."""
        ...

    def latest_for_production(self, production_id: str) -> ProductionScheduleSnapshot | None:
        """Return the latest schedule revision for one production."""
        ...

    def append_review(
        self,
        review: ProductionScheduleReviewRecord,
    ) -> ProductionScheduleReviewRecord:
        """Persist one immutable human review decision."""
        ...

    def reviews(
        self,
        schedule_id: str,
        revision: int,
    ) -> tuple[ProductionScheduleReviewRecord, ...]:
        """Return review decisions for one exact schedule revision."""
        ...


class ProductionSchedulePersistenceService:
    """Create durable schedule revisions without starting execution."""

    def __init__(
        self,
        scheduling: ProductionScheduleSource,
        repository: ProductionScheduleRepository,
    ) -> None:
        self.scheduling = scheduling
        self.repository = repository

    def create_revision(
        self,
        production_id: str,
        *,
        now: datetime | None = None,
    ) -> ProductionScheduleSnapshot:
        """Build and persist the next immutable schedule revision."""
        normalized = production_id.strip()
        if not normalized:
            raise ProductionSchedulePersistenceError("production_id cannot be blank")
        schedule = self.scheduling.schedule(normalized)
        latest = self.repository.latest_for_production(normalized)
        revision = 1 if latest is None else latest.revision + 1
        snapshot = ProductionScheduleSnapshot(
            schedule_id=_schedule_id(normalized),
            production_id=normalized,
            revision=revision,
            fingerprint=production_schedule_fingerprint(schedule),
            schedule=schedule,
            created_at=now or datetime.now(UTC),
        )
        return self.repository.save_snapshot(snapshot)

    def latest(self, production_id: str) -> ProductionScheduleSnapshot | None:
        """Return the latest persisted schedule revision for one production."""
        normalized = production_id.strip()
        if not normalized:
            raise ProductionSchedulePersistenceError("production_id cannot be blank")
        return self.repository.latest_for_production(normalized)

    def history(self, production_id: str) -> tuple[ProductionScheduleSnapshot, ...]:
        """Return immutable schedule history for one production."""
        normalized = production_id.strip()
        if not normalized:
            raise ProductionSchedulePersistenceError("production_id cannot be blank")
        return self.repository.history_for_production(normalized)


class ProductionScheduleReviewService:
    """Record explicit human review against exact durable schedule revisions."""

    def __init__(self, repository: ProductionScheduleRepository) -> None:
        self.repository = repository

    def review(
        self,
        schedule_id: str,
        revision: int,
        *,
        decision: ProductionScheduleReviewDecision,
        reviewed_by: str,
        notes: str,
        now: datetime | None = None,
    ) -> ProductionScheduleReviewRecord:
        """Approve or reject the current schedule revision exactly once."""
        normalized_schedule_id = schedule_id.strip()
        if not normalized_schedule_id:
            raise ProductionScheduleReviewError("schedule_id cannot be blank")
        actor = reviewed_by.strip()
        normalized_notes = notes.strip()
        if not actor:
            raise ProductionScheduleReviewError("reviewed_by is required")
        if not normalized_notes:
            raise ProductionScheduleReviewError("review notes are required")
        snapshot = self.repository.get_snapshot(normalized_schedule_id, revision)
        if snapshot is None:
            raise ProductionScheduleReviewError(
                f"ProductionSchedule revision not found: {normalized_schedule_id} r{revision}"
            )
        latest = self.repository.latest_for_production(snapshot.production_id)
        if latest is None or latest.revision != snapshot.revision:
            raise ProductionScheduleReviewError("Only the current schedule revision may be reviewed")
        if self.repository.reviews(snapshot.schedule_id, snapshot.revision):
            raise ProductionScheduleReviewError("Schedule revision has already been reviewed")
        record = ProductionScheduleReviewRecord(
            schedule_id=snapshot.schedule_id,
            production_id=snapshot.production_id,
            revision=snapshot.revision,
            fingerprint=snapshot.fingerprint,
            decision=decision,
            reviewed_by=actor,
            notes=normalized_notes,
            reviewed_at=now or datetime.now(UTC),
        )
        return self.repository.append_review(record)

    def view(self, schedule_id: str, revision: int) -> ProductionScheduleReviewView:
        """Return effective review state, including supersession by a newer revision."""
        normalized_schedule_id = schedule_id.strip()
        if not normalized_schedule_id:
            raise ProductionScheduleReviewError("schedule_id cannot be blank")
        snapshot = self.repository.get_snapshot(normalized_schedule_id, revision)
        if snapshot is None:
            raise ProductionScheduleReviewError(
                f"ProductionSchedule revision not found: {normalized_schedule_id} r{revision}"
            )
        reviews = self.repository.reviews(snapshot.schedule_id, snapshot.revision)
        review = reviews[-1] if reviews else None
        latest = self.repository.latest_for_production(snapshot.production_id)
        current = latest is not None and latest.revision == snapshot.revision
        if not current:
            state = ProductionScheduleReviewState.SUPERSEDED
        elif review is None:
            state = ProductionScheduleReviewState.PENDING_REVIEW
        elif review.decision is ProductionScheduleReviewDecision.APPROVED:
            state = ProductionScheduleReviewState.APPROVED
        else:
            state = ProductionScheduleReviewState.REJECTED
        return ProductionScheduleReviewView(
            snapshot=snapshot,
            review=review,
            state=state,
            current=current,
            can_review=current and review is None,
        )


def production_schedule_fingerprint(schedule: ProductionSchedule) -> str:
    """Return a deterministic fingerprint for provider-neutral schedule content."""
    payload = {
        "production_id": schedule.production_id,
        "assignments": [
            {
                "task_id": assignment.task_id,
                "resource_id": assignment.resource_id,
                "priority": int(assignment.priority),
                "required_capabilities": [
                    capability.value for capability in assignment.required_capabilities
                ],
            }
            for assignment in schedule.assignments
        ],
        "deferrals": [
            {
                "task_id": deferral.task_id,
                "reason": deferral.reason.value,
                "resource_ids": list(deferral.resource_ids),
            }
            for deferral in schedule.deferrals
        ],
        "ignored_task_ids": list(schedule.ignored_task_ids),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _schedule_id(production_id: str) -> str:
    digest = hashlib.sha256(production_id.encode("utf-8")).hexdigest()[:16].upper()
    return f"PS-{digest}"


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")
