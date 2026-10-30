"""Read-only governed planning chain discovery; hashes are not self-validating."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol
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
                        approved_story_id,
                        episode_id,
                        scene_id,
                        shot_id,
                        text_fields,
                        tuple(
                            sorted(
                                {str(item["asset_id"]) for item in linked if item.get("asset_id")}
                            )
                        ),
                        (str(hashes[0]), str(hashes[1]), str(hashes[2])),
                        tuple(str(item.get("status", "")) for item in linked),
                    )
                )
    return GovernedPlanningDiscovery(
        tuple(candidates),
        (
            *warnings,
            "Contract hashes have not been recomputed against their authoritative parent records; "
            "candidates are discovery-only, not freshness-verified CAP evidence.",
        ),
    )


class AuthoritativePlanningContracts(Protocol):
    """Existing production planner's hash calculator; no alternate algorithm allowed."""

    def episode_contract_hash(self, episode: dict[str, object]) -> str: ...

    def scene_contract_hash(self, scene: dict[str, object]) -> str: ...

    def shot_contract_hash(self, shot: dict[str, object]) -> str: ...


def verified_governed_shot_evidence(
    project_root: Path,
    approved_story_id: str,
    contracts: AuthoritativePlanningContracts,
) -> tuple[GovernedShotEvidence, ...]:
    """Forward only current source-verified evidence; fail closed for any mismatch."""
    episodes = _records(project_root, "episode_plans.json", "episodes")
    scenes = _records(project_root, "scene_plans.json", "scenes")
    shots = _records(project_root, "shot_plans.json", "shots")
    bindings = _records(project_root, "asset_resolutions.json", "bindings")
    discovered = discover_governed_shot_evidence(project_root, approved_story_id)
    if discovered.warnings[:-1]:
        raise ShotTextAuthorityError("; ".join(discovered.warnings[:-1]))
    verified: list[GovernedShotEvidence] = []
    for candidate in discovered.candidates:
        episode = next(
            (item for item in episodes if item.get("episode_id") == candidate.episode_id),
            None,
        )
        scene = next(
            (item for item in scenes if item.get("scene_id") == candidate.scene_id),
            None,
        )
        shot = next(
            (item for item in shots if item.get("shot_id") == candidate.shot_id),
            None,
        )
        if episode is None or scene is None or shot is None:
            raise ShotTextAuthorityError("Planning authority disappeared during verification")
        if episode.get("story_id") != approved_story_id:
            raise ShotTextAuthorityError("Cross-Story Episode is not authoritative")
        if (
            scene.get("episode_id") != candidate.episode_id
            or shot.get("scene_id") != candidate.scene_id
        ):
            raise ShotTextAuthorityError("Planning ownership changed during verification")
        linked = [item for item in bindings if item.get("shot_id") == candidate.shot_id]
        actual = (
            contracts.episode_contract_hash(episode),
            contracts.scene_contract_hash(scene),
            contracts.shot_contract_hash(shot),
        )
        if actual != candidate.contract_hashes:
            raise ShotTextAuthorityError(
                f"{candidate.shot_id}: planning contract hashes are stale or inconsistent"
            )
        if not linked or any(item.get("status") != "ready" for item in linked):
            raise ShotTextAuthorityError(
                f"{candidate.shot_id}: Draft or missing bindings are not approved evidence"
            )
        verified.append(candidate)
    # Re-read the four source collections: a concurrent update must not forward stale text.
    if (
        episodes != _records(project_root, "episode_plans.json", "episodes")
        or scenes != _records(project_root, "scene_plans.json", "scenes")
        or shots != _records(project_root, "shot_plans.json", "shots")
        or bindings != _records(project_root, "asset_resolutions.json", "bindings")
    ):
        raise ShotTextAuthorityError("Governed planning source changed during verification")
    return tuple(verified)
