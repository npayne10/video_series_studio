"""Read-only governed planning chain discovery; hashes are not self-validating."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class GovernedShotEvidence:
    story_id: str
    episode_id: str
    scene_id: str
    shot_id: str
    text_fields: tuple[tuple[str, str], ...]
    bound_asset_ids: tuple[str, ...]
    contract_hashes: tuple[str, str, str]
    binding_statuses: tuple[str, ...]


@dataclass(frozen=True)
class GovernedPlanningDiscovery:
    candidates: tuple[GovernedShotEvidence, ...]
    warnings: tuple[str, ...]
    hashes_verified: bool = False


def _records(root: Path, name: str, key: str) -> list[dict[str, object]]:
    path = root / "planning" / name
    if not path.is_file():
        raise ShotTextAuthorityError(f"Governed planning source missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload[key]
        if not isinstance(payload, dict) or not isinstance(records, list):
            raise ValueError("Invalid planning collection")
        if not all(isinstance(item, dict) for item in records):
            raise ValueError("Invalid planning record")
        return records
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ShotTextAuthorityError(f"Invalid governed planning source: {path}") from exc


def discover_governed_shot_evidence(
    project_root: Path, approved_story_id: str
) -> GovernedPlanningDiscovery:
    """Validate structural ownership only; never misstate hash shape as freshness."""
    episodes = _records(project_root, "episode_plans.json", "episodes")
    scenes = _records(project_root, "scene_plans.json", "scenes")
    shots = _records(project_root, "shot_plans.json", "shots")
    bindings = _records(project_root, "asset_resolutions.json", "bindings")
    candidates: list[GovernedShotEvidence] = []
    warnings: list[str] = []
    for episode in episodes:
        if episode.get("story_id") != approved_story_id:
            continue
        if episode.get("status") != "ready":
            warnings.append("Episode not ready")
            continue
        episode_id = str(episode.get("episode_id", ""))
        for scene in scenes:
            if scene.get("episode_id") != episode_id or scene.get("status") != "ready":
                continue
            scene_id = str(scene.get("scene_id", ""))
            for shot in shots:
                if shot.get("scene_id") != scene_id or shot.get("status") != "ready":
                    continue
                shot_id = str(shot.get("shot_id", ""))
                linked = [item for item in bindings if item.get("shot_id") == shot_id]
                hashes = (
                    scene.get("episode_contract_hash"),
                    shot.get("scene_contract_hash"),
                    next((item.get("shot_contract_hash") for item in linked), None),
                )
                if not all(isinstance(value, str) and _SHA256.fullmatch(value) for value in hashes):
                    warnings.append(f"{shot_id}: missing or malformed contract hashes")
                    continue
                if any(item.get("shot_contract_hash") != hashes[2] for item in linked):
                    warnings.append(f"{shot_id}: contradictory binding contract hashes")
                    continue
                if not linked:
                    warnings.append(f"{shot_id}: no asset bindings")
                    continue
                text_fields = tuple(
                    (field, value)
                    for field in ("required_action", "narrative_purpose", "production_objective")
                    if isinstance((value := shot.get(field)), str) and value.strip()
                )
                candidates.append(
                    GovernedShotEvidence(
                        approved_story_id, episode_id, scene_id, shot_id,
                        text_fields,
                        tuple(sorted({str(item["asset_id"]) for item in linked if item.get("asset_id")})),
                        (str(hashes[0]), str(hashes[1]), str(hashes[2])),
                        tuple(str(item.get("status", "")) for item in linked),
                    )
                )
    return GovernedPlanningDiscovery(
        tuple(candidates),
        tuple(warnings) + (
            "Contract hashes have not been recomputed against their authoritative parent records; "
            "candidates are discovery-only, not freshness-verified CAP evidence.",
        ),
    )
