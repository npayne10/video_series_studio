"""Focused regression tests for Phase 19.6.7 schedule persistence and review."""

from datetime import UTC, datetime

import pytest

from vscs.application.production_tasks import (
    ProductionCapability,
    ProductionSchedule,
    ProductionScheduleAssignment,
    ProductionScheduleDeferral,
    ProductionSchedulePersistenceError,
    ProductionSchedulePersistenceService,
    ProductionScheduleRepository,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewError,
    ProductionScheduleReviewRecord,
    ProductionScheduleReviewService,
    ProductionScheduleReviewState,
    ProductionScheduleSnapshot,
    ProductionSchedulingDeferralReason,
    ProductionTaskPriority,
    production_schedule_fingerprint,
)

_NOW = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


def _schedule(*, resource_id: str = "RESOURCE-A") -> ProductionSchedule:
    return ProductionSchedule(
        production_id="PROD-001",
        assignments=(
            ProductionScheduleAssignment(
                task_id="PT-A",
                resource_id=resource_id,
                priority=ProductionTaskPriority.HIGH,
                required_capabilities=(ProductionCapability.VIDEO_GENERATION,),
            ),
        ),
        deferrals=(
            ProductionScheduleDeferral(
                task_id="PT-B",
                reason=ProductionSchedulingDeferralReason.RESOURCE_ALREADY_ASSIGNED,
                resource_ids=(resource_id,),
            ),
        ),
        ignored_task_ids=("PT-C",),
    )


class _Scheduling:
    def __init__(self, schedule: ProductionSchedule) -> None:
        self.current = schedule
        self.requested: list[str] = []

    def schedule(self, production_id: str) -> ProductionSchedule:
        self.requested.append(production_id)
        return self.current


class _Repository(ProductionScheduleRepository):
    def __init__(self) -> None:
        self.snapshots: list[ProductionScheduleSnapshot] = []
        self.review_records: list[ProductionScheduleReviewRecord] = []

    def save_snapshot(self, snapshot: ProductionScheduleSnapshot) -> ProductionScheduleSnapshot:
        self.snapshots.append(snapshot)
        return snapshot

    def get_snapshot(self, schedule_id: str, revision: int) -> ProductionScheduleSnapshot | None:
        return next(
            (
                item
                for item in self.snapshots
                if item.schedule_id == schedule_id and item.revision == revision
            ),
            None,
        )

    def history_for_production(
        self,
        production_id: str,
    ) -> tuple[ProductionScheduleSnapshot, ...]:
        return tuple(item for item in self.snapshots if item.production_id == production_id)

    def latest_for_production(self, production_id: str) -> ProductionScheduleSnapshot | None:
        history = self.history_for_production(production_id)
        return history[-1] if history else None

    def append_review(
        self,
        review: ProductionScheduleReviewRecord,
    ) -> ProductionScheduleReviewRecord:
        self.review_records.append(review)
        return review

    def reviews(
        self,
        schedule_id: str,
        revision: int,
    ) -> tuple[ProductionScheduleReviewRecord, ...]:
        return tuple(
            item
            for item in self.review_records
            if item.schedule_id == schedule_id and item.revision == revision
        )


def test_schedule_fingerprint_is_deterministic_and_content_sensitive() -> None:
    first = production_schedule_fingerprint(_schedule())
    second = production_schedule_fingerprint(_schedule())
    changed = production_schedule_fingerprint(_schedule(resource_id="RESOURCE-B"))

    assert first == second
    assert first != changed


def test_persistence_creates_monotonic_revisions_without_overwriting_history() -> None:
    scheduling = _Scheduling(_schedule())
    repository = _Repository()
    service = ProductionSchedulePersistenceService(scheduling, repository)  # type: ignore[arg-type]

    first = service.create_revision(" PROD-001 ", now=_NOW)
    scheduling.current = _schedule(resource_id="RESOURCE-B")
    second = service.create_revision("PROD-001", now=_NOW)

    assert scheduling.requested == ["PROD-001", "PROD-001"]
    assert first.schedule_id == second.schedule_id
    assert first.revision == 1
    assert second.revision == 2
    assert first.fingerprint != second.fingerprint
    assert service.history("PROD-001") == (first, second)
    assert service.latest("PROD-001") == second


def test_persistence_rejects_blank_production_identity() -> None:
    service = ProductionSchedulePersistenceService(_Scheduling(_schedule()), _Repository())  # type: ignore[arg-type]

    with pytest.raises(ProductionSchedulePersistenceError, match="production_id cannot be blank"):
        service.create_revision(" ")


def test_review_records_explicit_human_decision_against_exact_fingerprint() -> None:
    repository = _Repository()
    persistence = ProductionSchedulePersistenceService(_Scheduling(_schedule()), repository)  # type: ignore[arg-type]
    snapshot = persistence.create_revision("PROD-001", now=_NOW)
    reviews = ProductionScheduleReviewService(repository)

    record = reviews.review(
        snapshot.schedule_id,
        snapshot.revision,
        decision=ProductionScheduleReviewDecision.APPROVED,
        reviewed_by=" Neill ",
        notes=" Approved resource allocation. ",
        now=_NOW,
    )

    assert record.fingerprint == snapshot.fingerprint
    assert record.reviewed_by == "Neill"
    assert record.notes == "Approved resource allocation."
    view = reviews.view(snapshot.schedule_id, snapshot.revision)
    assert view.state is ProductionScheduleReviewState.APPROVED
    assert view.current
    assert not view.can_review


def test_review_requires_human_identity_and_notes() -> None:
    repository = _Repository()
    snapshot = ProductionSchedulePersistenceService(
        _Scheduling(_schedule()), repository
    ).create_revision(  # type: ignore[arg-type]
        "PROD-001",
        now=_NOW,
    )
    service = ProductionScheduleReviewService(repository)

    with pytest.raises(ProductionScheduleReviewError, match="reviewed_by is required"):
        service.review(
            snapshot.schedule_id,
            1,
            decision=ProductionScheduleReviewDecision.APPROVED,
            reviewed_by=" ",
            notes="Valid notes",
        )
    with pytest.raises(ProductionScheduleReviewError, match="review notes are required"):
        service.review(
            snapshot.schedule_id,
            1,
            decision=ProductionScheduleReviewDecision.REJECTED,
            reviewed_by="Reviewer",
            notes=" ",
        )


def test_schedule_revision_can_only_be_reviewed_once() -> None:
    repository = _Repository()
    snapshot = ProductionSchedulePersistenceService(
        _Scheduling(_schedule()), repository
    ).create_revision(  # type: ignore[arg-type]
        "PROD-001",
        now=_NOW,
    )
    service = ProductionScheduleReviewService(repository)
    service.review(
        snapshot.schedule_id,
        1,
        decision=ProductionScheduleReviewDecision.REJECTED,
        reviewed_by="Reviewer",
        notes="Resource allocation requires revision",
        now=_NOW,
    )

    with pytest.raises(ProductionScheduleReviewError, match="already been reviewed"):
        service.review(
            snapshot.schedule_id,
            1,
            decision=ProductionScheduleReviewDecision.APPROVED,
            reviewed_by="Reviewer",
            notes="Changed decision",
            now=_NOW,
        )


def test_newer_schedule_revision_supersedes_older_review_without_erasing_history() -> None:
    repository = _Repository()
    scheduling = _Scheduling(_schedule())
    persistence = ProductionSchedulePersistenceService(scheduling, repository)  # type: ignore[arg-type]
    reviews = ProductionScheduleReviewService(repository)
    first = persistence.create_revision("PROD-001", now=_NOW)
    approved = reviews.review(
        first.schedule_id,
        first.revision,
        decision=ProductionScheduleReviewDecision.APPROVED,
        reviewed_by="Reviewer",
        notes="Approved",
        now=_NOW,
    )

    scheduling.current = _schedule(resource_id="RESOURCE-B")
    second = persistence.create_revision("PROD-001", now=_NOW)

    old_view = reviews.view(first.schedule_id, first.revision)
    new_view = reviews.view(second.schedule_id, second.revision)
    assert old_view.state is ProductionScheduleReviewState.SUPERSEDED
    assert old_view.review == approved
    assert not old_view.current
    assert new_view.state is ProductionScheduleReviewState.PENDING_REVIEW
    assert new_view.can_review

    with pytest.raises(ProductionScheduleReviewError, match="Only the current schedule revision"):
        reviews.review(
            first.schedule_id,
            first.revision,
            decision=ProductionScheduleReviewDecision.REJECTED,
            reviewed_by="Reviewer",
            notes="Too late",
        )


def test_rejected_current_schedule_remains_reviewable_history_not_execution_authority() -> None:
    repository = _Repository()
    snapshot = ProductionSchedulePersistenceService(
        _Scheduling(_schedule()), repository
    ).create_revision(  # type: ignore[arg-type]
        "PROD-001",
        now=_NOW,
    )
    service = ProductionScheduleReviewService(repository)

    service.review(
        snapshot.schedule_id,
        snapshot.revision,
        decision=ProductionScheduleReviewDecision.REJECTED,
        reviewed_by="Reviewer",
        notes="Defer until another resource is available",
        now=_NOW,
    )

    view = service.view(snapshot.schedule_id, snapshot.revision)
    assert view.state is ProductionScheduleReviewState.REJECTED
    assert view.snapshot.schedule == _schedule()
    assert not view.can_review
