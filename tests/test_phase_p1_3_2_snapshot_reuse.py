"""P1.3.2: readiness snapshots are memoized only within a UI selection."""

from unittest.mock import Mock

import pytest

from vscs.application.selection_package_cache import selection_package_scope
from vscs.application.story.planning_review import GovernedPlanningReviewService


def test_repeated_snapshot_within_selection_computes_once():
    service = object.__new__(GovernedPlanningReviewService)
    snapshot = object()
    service._snapshot_uncached = Mock(return_value=snapshot)
    with selection_package_scope():
        assert service.snapshot(" sht-001 ") is snapshot
        assert service.snapshot("SHT-001") is snapshot
    service._snapshot_uncached.assert_called_once_with(" sht-001 ")


def test_new_selection_recomputes_planning_readiness():
    service = object.__new__(GovernedPlanningReviewService)
    ready, stale = object(), object()
    service._snapshot_uncached = Mock(side_effect=[ready, stale])
    with selection_package_scope():
        assert service.snapshot("SHT-001") is ready
    with selection_package_scope():
        assert service.snapshot("SHT-001") is stale
    assert service._snapshot_uncached.call_count == 2


def test_outside_selection_always_checks_authority():
    service = object.__new__(GovernedPlanningReviewService)
    service._snapshot_uncached = Mock(side_effect=[object(), object()])
    assert service.snapshot("SHT-001") is not service.snapshot("SHT-001")
    assert service._snapshot_uncached.call_count == 2


def test_failed_snapshot_is_not_cached():
    service = object.__new__(GovernedPlanningReviewService)
    recovered = object()
    service._snapshot_uncached = Mock(side_effect=[ValueError("bad snapshot"), recovered])
    with selection_package_scope():
        with pytest.raises(ValueError, match="bad snapshot"):
            service.snapshot("SHT-001")
        assert service.snapshot("SHT-001") is recovered
    assert service._snapshot_uncached.call_count == 2
