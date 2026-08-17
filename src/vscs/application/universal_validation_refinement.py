"""Cross-authority validation refinements for Phase 19.4 provider readiness."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
)


def install_universal_validation_refinement() -> None:
    """Install runtime consistency validation once.

    Performer and canonical-reference consistency is owned by the base Universal
    Production Description compiler, where governed Shot asset bindings are the
    sole performer authority. This refinement must never infer performer identity
    from free-form Action & Performance prose.
    """
    service_type: Any = UniversalProductionDescriptionCompilerService
    if getattr(service_type, "_phase_19_4_9_validation_refined", False):
        return

    original: Callable[[dict[str, Any]], tuple[str, ...]] = service_type._consistency_findings

    def refined(cls: type[Any], description: dict[str, Any]) -> tuple[str, ...]:
        findings = list(original(description))
        shot = _dict_value(description.get("shot"))
        action = _dict_value(description.get("action_performance"))

        shot_runtime = _numeric_runtime(shot.get("target_runtime_seconds"))
        action_runtime = _action_runtime_seconds(action)
        if (
            shot_runtime is not None
            and action_runtime is not None
            and abs(shot_runtime - action_runtime) > 0.01
        ):
            findings.append(
                f"Shot target runtime is {_format_seconds(shot_runtime)} seconds, but "
                f"Action & Performance timing specifies {_format_seconds(action_runtime)} seconds."
            )

        return tuple(dict.fromkeys(findings))

    service_type._consistency_findings = classmethod(refined)
    service_type.SCHEMA_VERSION = "1.4"
    service_type._phase_19_4_9_validation_refined = True


def _numeric_runtime(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"\d+(?:\.\d+)?", value)
        if match is not None:
            return float(match.group(0))
    return None


def _action_runtime_seconds(action: dict[str, Any]) -> float | None:
    for key in ("target_runtime_seconds", "runtime_seconds", "duration_seconds"):
        runtime = _numeric_runtime(action.get(key))
        if runtime is not None:
            return runtime
    timing_notes = str(action.get("timing_notes", ""))
    match = re.search(
        r"(?:target\s+runtime|runtime|duration)\s*:?\s*(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b",
        timing_notes,
        flags=re.IGNORECASE,
    )
    return float(match.group(1)) if match is not None else None


def _format_seconds(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
