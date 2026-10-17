"""Phase P1.3: selection-local memoization never persists governance decisions."""

import pytest

from vscs.application.selection_package_cache import (
    selection_package_lookup,
    selection_package_scope,
)


def test_identical_package_lookup_computed_once_per_selection():
    service = object()
    calls = []

    def compute():
        calls.append(1)
        return "package"

    with selection_package_scope():
        assert selection_package_lookup(service, "sht-1", compute) == "package"
        assert selection_package_lookup(service, "SHT-1", compute) == "package"
    assert len(calls) == 1


def test_new_selection_rechecks_authoritative_state():
    service = object()
    source = {"result": "approved"}

    with selection_package_scope():
        assert selection_package_lookup(service, "SHT-1", lambda: source["result"]) == "approved"
        source["result"] = "stale"
        assert selection_package_lookup(service, "SHT-1", lambda: source["result"]) == "approved"
    with selection_package_scope():
        assert selection_package_lookup(service, "SHT-1", lambda: source["result"]) == "stale"


def test_outside_selection_never_caches():
    service = object()
    calls = []

    def compute():
        calls.append(len(calls) + 1)
        return len(calls)

    assert selection_package_lookup(service, "SHT-1", compute) == 1
    assert selection_package_lookup(service, "SHT-1", compute) == 2


def test_exception_discards_selection_cache():
    service = object()
    with pytest.raises(RuntimeError, match="stop"), selection_package_scope():
        assert selection_package_lookup(service, "SHT-1", lambda: "old") == "old"
        raise RuntimeError("stop")
    with selection_package_scope():
        assert selection_package_lookup(service, "SHT-1", lambda: "new") == "new"


def test_different_services_and_shots_are_isolated():
    first, second = object(), object()
    with selection_package_scope():
        assert selection_package_lookup(first, "A", lambda: 1) == 1
        assert selection_package_lookup(first, "B", lambda: 2) == 2
        assert selection_package_lookup(second, "A", lambda: 3) == 3
