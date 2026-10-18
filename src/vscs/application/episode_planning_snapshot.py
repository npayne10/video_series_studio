"""Immutable operator-authorized Episode planning snapshots for partial Draft scope."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vscs.application.assembly_contracts import AssemblyScope, AssemblyScopeKind


@dataclass(frozen=True)
class PlanningSnapshot:
    episode_id: str
    production_id: str
    shot_ids: tuple[str, ...]
    planning_fingerprint: str
    operator_id: str
    revision_id: str

    @property
    def scope(self) -> AssemblyScope:
        return AssemblyScope(
            production_id=self.production_id,
            scope_kind=AssemblyScopeKind.EPISODE,
            scope_id=self.episode_id,
            declared_shot_set_revision=self.revision_id,
            story_structure_fingerprint=self.planning_fingerprint,
        )


def build_planning_snapshot(
    episode_id: str,
    planning_services: tuple[Any, Any, Any, Any],
    production_ids: tuple[str, ...],
    operator_id: str,
) -> PlanningSnapshot:
    """Operator authorizes exactly the current plan, not incomplete Shot approvals."""
    episodes, scenes, shots, _reviews = planning_services
    episode = episodes.plan(episode_id)
    if episode is None or not episode.production_ready:
        raise ValueError("Episode plan is not Ready")
    scene_plans = scenes.list_plans(episode_id=episode_id)
    if not scene_plans or not all(scenes.is_production_ready(scene) for scene in scene_plans):
        raise ValueError("Scene planning authority is incomplete or not Ready")
    required: list[str] = []
    structure: list[dict[str, Any]] = []
    for scene in scene_plans:
        plans = shots.list_plans(scene_id=scene.scene_id)
        if not plans:
            raise ValueError("Scene has no governed Shot Plans")
        ids = [plan.shot_id for plan in plans]
        required.extend(ids)
        structure.append({"scene_id": scene.scene_id, "shots": [asdict(plan) for plan in plans]})
    if len(required) != len(set(required)):
        raise ValueError("Duplicate planned Shots")
    unique_productions = sorted(set(production_ids))
    if len(unique_productions) != 1 or not unique_productions[0]:
        raise ValueError("A single persisted production identity is required")
    if not operator_id.strip():
        raise ValueError("Explicit operator identity is required")
    payload = {
        "episode_id": episode_id,
        "story_id": episode.story_id,
        "episode_plan": asdict(episode),
        "scenes": [asdict(scene) for scene in scene_plans],
        "shot_structure": structure,
        "required_shots": required,
        "production_id": unique_productions[0],
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return PlanningSnapshot(
        episode_id,
        unique_productions[0],
        tuple(required),
        fingerprint,
        operator_id.strip(),
        "PS-" + fingerprint[:24].upper(),
    )


class JsonPlanningSnapshotRepository:
    """Append-only operator authorization; cannot approve media or close an Episode."""

    def __init__(self, project_directory: Path):
        self.root = Path(project_directory) / ".vscs" / "episode_assembly" / "planning_snapshots"

    def _path(self, episode_id: str, revision_id: str) -> Path:
        for value in (episode_id, revision_id):
            if not value or any(
                ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
                for ch in value
            ):
                raise ValueError("Unsafe snapshot identity")
        return self.root / episode_id / f"{revision_id}.json"

    def create(self, snapshot: PlanningSnapshot) -> Path:
        path = self._path(snapshot.episode_id, snapshot.revision_id)
        if path.exists():
            raise ValueError("Planning snapshot already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        staged: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                suffix=".tmp",
                delete=False,
            ) as stream:
                staged = Path(stream.name)
                payload = asdict(snapshot)
                serialized = json.dumps(payload, sort_keys=True)
                integrity = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
                json.dump(
                    {"schema_version": "1.0", "snapshot": payload, "integrity_sha256": integrity},
                    stream,
                    sort_keys=True,
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.link(staged, path)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
        return path

    def get(self, episode_id: str, revision_id: str) -> PlanningSnapshot | None:
        path = self._path(episode_id, revision_id)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != "1.0":
            raise ValueError("Unsupported planning snapshot schema")
        serialized = json.dumps(raw["snapshot"], sort_keys=True)
        actual_integrity = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        if actual_integrity != raw.get("integrity_sha256"):
            raise ValueError("Planning snapshot integrity mismatch")
        snapshot = PlanningSnapshot(
            **{**raw["snapshot"], "shot_ids": tuple(raw["snapshot"]["shot_ids"])}
        )
        if snapshot.episode_id != episode_id or snapshot.revision_id != revision_id:
            raise ValueError("Planning snapshot identity mismatch")
        if not snapshot.shot_ids or len(set(snapshot.shot_ids)) != len(snapshot.shot_ids):
            raise ValueError("Invalid snapshot Shot set")
        if not snapshot.operator_id.strip() or not snapshot.production_id.strip():
            raise ValueError("Planning snapshot lacks authority")
        if "PS-" + snapshot.planning_fingerprint[:24].upper() != snapshot.revision_id:
            raise ValueError("Planning snapshot fingerprint identity mismatch")
        if not isinstance(snapshot.scope, AssemblyScope):
            raise ValueError("Invalid scope")
        return snapshot

    def current(self, episode_id: str, expected: PlanningSnapshot) -> AssemblyScope | None:
        snapshot = self.get(episode_id, expected.revision_id)
        if snapshot is None:
            return None
        if snapshot != expected:
            raise ValueError("Published planning snapshot is stale or differs from current plan")
        return snapshot.scope


def resolve_current_planning_snapshot(
    project_directory: Path,
    episode_id: str,
    planning_services: tuple[Any, Any, Any, Any],
    production_ids: tuple[str, ...],
    expected_shot_ids: tuple[str, ...],
) -> AssemblyScope | None:
    """Accept only published, intact snapshot matching the *current* plan."""
    if not expected_shot_ids:
        return None
    candidate = build_planning_snapshot(
        episode_id, planning_services, production_ids, operator_id="comparison-only"
    )
    if candidate.shot_ids != expected_shot_ids:
        raise ValueError("Episode Shot order differs from planning snapshot authority")
    repository = JsonPlanningSnapshotRepository(project_directory)
    persisted = repository.get(episode_id, candidate.revision_id)
    if persisted is None:
        return None
    if (
        persisted.production_id != candidate.production_id
        or persisted.shot_ids != candidate.shot_ids
        or persisted.planning_fingerprint != candidate.planning_fingerprint
    ):
        raise ValueError("Persisted planning snapshot does not match current authority")
    return persisted.scope
