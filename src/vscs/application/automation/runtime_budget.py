"""Deterministic runtime-budget fitting shared by automation orchestration."""

from __future__ import annotations


def fit_positive_runtimes_to_budget(
    runtimes: tuple[int, ...],
    budget_seconds: int,
) -> tuple[int, ...]:
    """Fit positive runtime estimates into a parent budget while preserving relative pacing.

    This is the same largest-remainder policy established by Phase 19.5.4: every item
    retains at least one second, relative provider pacing is preserved as closely as
    integer runtimes allow, and the fitted total exactly equals the budget only when
    the original estimates exceed it.
    """
    if budget_seconds <= 0:
        raise ValueError("Runtime budget must be positive")
    if not runtimes:
        return ()
    if any(runtime <= 0 for runtime in runtimes):
        raise ValueError("Runtime estimates must all be positive")
    if budget_seconds < len(runtimes):
        raise ValueError(
            f"Runtime budget {budget_seconds}s is too short for {len(runtimes)} positive items"
        )

    total = sum(runtimes)
    if total <= budget_seconds:
        return runtimes

    distributable = budget_seconds - len(runtimes)
    weights = tuple(runtime / total for runtime in runtimes)
    raw_extra = tuple(weight * distributable for weight in weights)
    extras = [int(value) for value in raw_extra]
    remainder = distributable - sum(extras)
    order = sorted(
        range(len(extras)),
        key=lambda index: (raw_extra[index] - extras[index], -index),
        reverse=True,
    )
    for index in order[:remainder]:
        extras[index] += 1
    return tuple(1 + extras[index] for index in range(len(runtimes)))
