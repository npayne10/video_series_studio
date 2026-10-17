"""Opt-in timing diagnostics for Production Planning shot switches."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
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
