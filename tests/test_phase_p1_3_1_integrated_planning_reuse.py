"""P1.3.1: governed planning reuse is limited to a selection event."""

from unittest.mock import Mock

from vscs.application.selection_package_cache import selection_package_scope
from vscs.application.story.planning_integration import GovernedPlanningIntegrationService


def test_integrated_package_reused_per_selection():
    service = object.__new__(GovernedPlanningIntegrationService)
    service._current_package_uncached = Mock(return_value=None)
    with selection_package_scope():
        assert service.current_package(" sht-1 ") is None
        assert service.current_package("SHT-1") is None
    service._current_package_uncached.assert_called_once_with(" sht-1 ")


def test_integrated_package_rechecked_on_next_selection():
    service = object.__new__(GovernedPlanningIntegrationService)
    service._current_package_uncached = Mock(side_effect=[object(), None])
    with selection_package_scope():
        first = service.current_package("SHT-1")
        assert service.current_package("SHT-1") is first
    with selection_package_scope():
        assert service.current_package("SHT-1") is None
    assert service._current_package_uncached.call_count == 2


def test_integrated_package_lookup_outside_selection_is_live():
    service = object.__new__(GovernedPlanningIntegrationService)
    service._current_package_uncached = Mock(side_effect=[object(), None])
    assert service.current_package("SHT-1") is not None
    assert service.current_package("SHT-1") is None
    assert service._current_package_uncached.call_count == 2


def test_integrated_package_is_current_reuses_authoritative_result():
    service = object.__new__(GovernedPlanningIntegrationService)
    package = Mock(shot_id="SHT-1", package_id="PIP-1")
    service._current_package_uncached = Mock(return_value=package)
    with selection_package_scope():
        assert service.is_current(package)
        assert service.is_current(package)
    service._current_package_uncached.assert_called_once_with("SHT-1")
