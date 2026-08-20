"""Production execution profiles used for package, attempt, and retry scope."""

from __future__ import annotations

from enum import StrEnum


class ProductionExecutionProfile(StrEnum):
    """Supported operator-selected production quality profiles."""

    PREVIEW = "preview"
    PRODUCTION = "production"
    MASTER = "master"


def normalize_execution_profile(value: str) -> str:
    """Return one canonical supported execution profile value."""
    normalized = value.strip().casefold() or ProductionExecutionProfile.PRODUCTION.value
    try:
        return ProductionExecutionProfile(normalized).value
    except ValueError as exc:
        supported = ", ".join(item.value for item in ProductionExecutionProfile)
        raise ValueError(
            f"Unsupported production execution profile {value!r}; expected {supported}"
        ) from exc
