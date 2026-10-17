"""P1.3.3 governed continuity predecessor selection regression tests."""

from types import SimpleNamespace
from unittest.mock import Mock

from vscs.application.continuity_compiler import ContinuityCompilerService


def _compiler(ids, current_ids):
    planning = Mock()
    planning.list_packages.return_value = tuple(SimpleNamespace(shot_id=s) for s in ids)
    planning.current_package.side_effect = lambda shot: (
        SimpleNamespace(shot_id=shot) if shot in current_ids else None
    )
    packages = Mock()
    packages.planning = planning
    packages.current_package.side_effect = lambda shot: f"production:{shot}"
    compiler = object.__new__(ContinuityCompilerService)
    compiler.packages = packages
    return compiler, planning, packages


def test_nearest_current_predecessor_skips_stale_and_future():
    compiler, planning, packages = _compiler(
        ["SHT-001", "SHT-002", "SHT-003", "SHT-004", "SHT-005"],
        {"SHT-001", "SHT-003", "SHT-005"},
    )
    assert compiler._previous_package("SHT-005") == "production:SHT-003"
    planning.current_package.assert_any_call("SHT-005")
    planning.current_package.assert_any_call("SHT-004")
    planning.current_package.assert_any_call("SHT-003")
    packages.current_package.assert_called_once_with("SHT-003")


def test_stale_selected_shot_has_no_predecessor():
    compiler, planning, packages = _compiler(
        ["SHT-001", "SHT-002"], {"SHT-001"}
    )
    assert compiler._previous_package("SHT-002") is None
    packages.current_package.assert_not_called()


def test_duplicate_historical_revisions_evaluated_once_per_shot():
    compiler, planning, packages = _compiler(
        ["SHT-001", "SHT-001", "SHT-002", "SHT-002"], {"SHT-001", "SHT-002"}
    )
    assert compiler._previous_package("SHT-002") == "production:SHT-001"
    assert planning.current_package.call_count == 2


def test_reference_precedence_is_unchanged():
    compiler, planning, packages = _compiler(["SHT-001", "SHT-002"], {"SHT-002"})
    assert compiler._previous_package(
        "SHT-002", referenced_shot_id="SHT-009"
    ) == "production:SHT-009"
    planning.list_packages.assert_not_called()
