"""Opt-in timing diagnostics for Production Planning shot switches."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable, Iterator
from typing import Any, TypeVar
from contextlib import contextmanager

_LOG = logging.getLogger("vscs.performance.shot_switch")


@contextmanager
def measure_shot_switch(stage: str) -> Iterator[None]:
    """Report synchronous elapsed time without modifying application state."""
    if os.environ.get("VSCS_SHOT_SWITCH_PROFILE") != "1":
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        _LOG.warning("SHOT_SWITCH_PROFILE stage=%s duration_ms=%.2f", stage, elapsed_ms)


_R = TypeVar("_R")


def profile_selection_handler(handler: Callable[..., _R], stage: str) -> Callable[..., _R]:
    """Wrap a selection callback without modifying its arguments or return value."""
    def measured(*args: Any, **kwargs: Any) -> _R:
        with measure_shot_switch(stage):
            return handler(*args, **kwargs)

    return measured
