"""Cross-authority validation refinements for Phase 19.4 provider readiness."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
)

_NON_PERFORMER_NAMES = frozenset(
    {
        "A",
        "An",
        "And",
        "Bridge",
        "Crew",
        "He",
        "Her",
        "His",
        "It",
        "No",
        "None",
        "She",
        "Shot",
        "That",
        "The",
        "Their",
        "They",
        "This",
        "We",
    }
)
_CHARACTER_CATEGORIES = frozenset({"character", "person", "performer"})


def install_universal_validation_refinement() -> None:
    """Install runtime and canonical performer coverage validation once."""
    service_type: Any = UniversalProductionDescriptionCompilerService
    if getattr(service_type, "_phase_19_4_9_validation_refined", False):
        return

    original: Callable[[dict[str, Any]], tuple[str, ...]] = service_type._consistency_findings

    def refined(cls: type[Any], description: dict[str, Any]) -> tuple[str, ...]:
        findings = list(original(description))
        shot = _dict_value(description.get("shot"))
        action = _dict_value(description.get("action_performance"))
        assets_raw = description.get("assets", [])
        assets = [_dict_value(item) for item in assets_raw if isinstance(item, dict)]

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

        performers = _named_performers(action)
        missing = _missing_performer_coverage(performers, assets)
        if missing:
            findings.append(
                "Action & Performance performers lack governed character assets with canonical "
                "references: " + ", ".join(missing) + "."
            )
        return tuple(dict.fromkeys(findings))

    service_type._consistency_findings = classmethod(refined)
    service_type.SCHEMA_VERSION = "1.3"
    service_type._phase_19_4_9_validation_refined = True


def _named_performers(action: dict[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    spoken = str(action.get("spoken_content", ""))
    for match in re.finditer(r"(?:^|\n)\s*([A-Z][A-Za-z0-9 .'-]{0,50})\s*:", spoken):
        name = match.group(1).strip()
        if name not in names:
            names.append(name)

    narrative = "\n".join(
        str(action.get(key, ""))
        for key in (
            "temporal_narrative",
            "performance_direction",
            "opening_state",
            "closing_state",
        )
    )
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", narrative):
        candidate = match.group(1).strip()
        if candidate in _NON_PERFORMER_NAMES or candidate in names:
            continue
        names.append(candidate)
    return tuple(names)


def _missing_performer_coverage(
    performers: tuple[str, ...], assets: list[dict[str, Any]]
) -> tuple[str, ...]:
    missing: list[str] = []
    for performer in performers:
        matching = [asset for asset in assets if _asset_mentions_name(asset, performer)]
        if matching and not any(_is_character_asset(asset) for asset in matching):
            # A named ship/location/other asset is not a performer and should not be misclassified.
            continue
        if not any(
            _is_character_asset(asset) and _asset_has_canonical_reference(asset)
            for asset in matching
        ):
            missing.append(performer)
    return tuple(missing)


def _asset_mentions_name(asset: dict[str, Any], name: str) -> bool:
    searchable = " ".join(
        str(asset.get(key, ""))
        for key in (
            "asset_id",
            "name",
            "title",
            "role",
            "requirement",
            "canonical_reference",
        )
    ).lower()
    return name.lower() in searchable


def _is_character_asset(asset: dict[str, Any]) -> bool:
    return str(asset.get("category", "")).strip().lower() in _CHARACTER_CATEGORIES


def _asset_has_canonical_reference(asset: dict[str, Any]) -> bool:
    if str(asset.get("canonical_reference", "")).strip():
        return True
    references = asset.get("canonical_references", [])
    return isinstance(references, list | tuple) and any(
        isinstance(item, dict) and str(item.get("file_path", "")).strip() for item in references
    )


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
