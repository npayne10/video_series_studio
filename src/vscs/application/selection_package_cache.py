"""Selection-local memoization for repeated read-only package lookups.

No persistent cache: results are discarded when the UI selection callback exits.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_CACHE: ContextVar[dict[tuple[int, str], Any] | None] = ContextVar(
    "vscs_selection_package_cache", default=None
)


@contextmanager
def selection_package_scope() -> Iterator[None]:
    """One fresh cache for the entire synchronous selection callback."""
    token = _CACHE.set({})
    try:
        yield
    finally:
        _CACHE.reset(token)


def selection_package_lookup[T](
    service: object, shot_id: str, compute: Callable[[], T]
) -> T:
    """Reuse a read-only result only while a selection scope is active."""
    cache = _CACHE.get()
    if cache is None:
        return compute()
    key = (id(service), shot_id.strip().upper())
    if key not in cache:
        cache[key] = compute()
    return cache[key]
