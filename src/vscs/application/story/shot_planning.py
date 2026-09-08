"""Governed Shot Planning for Phase 19.3.3."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from math import ceil
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.application.shots import ProductionShot, ShotPlanningService

from .iterative_scene_planning import IterativeScenePlanningService
from .scene_planning import ScenePlan, ScenePlanStatus


class GovernedShotPlanningError(RuntimeError):
    """Raised when an authoritative Shot Plan cannot be processed safely."""


@dataclass(frozen=True, slots=True)
class HardwareAwareShotReplanProposal:
    """Preview of a hardware-bounded replacement Shot Plan for one Ready Scene."""

    scene_id: str
    hardware_label: str
    maximum_shot_runtime_seconds: int
    current_shot_count: int
    proposed_shot_count: int
    scene_runtime_seconds: int
    semantic_source: str
    semantic_source_shot_count: int
    proposed_shots: tuple[ShotPlan, ...]


@dataclass(frozen=True, slots=True)
class HardwareAwareShotReplanResult:
    """Durable result after a human-approved hardware-aware Scene replan."""

    scene_id: str
    maximum_shot_runtime_seconds: int
    previous_shot_count: int
    new_shot_count: int
    archive_path: Path | None
    shots: tuple[ShotPlan, ...]


class ShotPlanStatus(StrEnum):
    """Minimal governance state for specialist production planning."""

    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class ShotPlan:
    """Renderer-neutral shot intent owned by the authoritative Shot Planner."""

    shot_id: str
    scene_id: str
    sequence_number: int
    title: str
    narrative_purpose: str
    production_objective: str
    target_runtime_seconds: int
    required_action: str
    dialogue_requirement: str = ""
    continuity_in: str = ""
    continuity_out: str = ""
    shot_constraints: tuple[str, ...] = ()
    scene_contract_hash: str = ""
    status: ShotPlanStatus = ShotPlanStatus.DRAFT


class GovernedShotPlanningService:
    """Persist lean Shot Plans beneath authoritative Ready Scene Plans."""

    FILE_NAME = "shot_plans.json"
    SCHEMA_VERSION = "1.1"
    HISTORY_DIRECTORY = "shot_plan_history"
    DEFAULT_HARDWARE_SHOT_LIMIT_SECONDS = 7
    HARDWARE_CAPABILITY_FILE = Path(".vscs") / "provider_executions" / "hardware_capability.json"

    def __init__(
        self,
        projects: ProjectService,
        scenes: IterativeScenePlanningService,
        legacy_shots: ShotPlanningService,
    ) -> None:
        self.projects = projects
        self.scenes = scenes
        self.legacy_shots = legacy_shots

    @property
    def planning_file(self) -> Path:
        """Return the active project's governed Shot Planner file."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "planning" / self.FILE_NAME

    def hardware_capability(self) -> dict[str, Any]:
        """Return persisted provider hardware authority or the conservative safe default."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        path = self.projects.project_directory / self.HARDWARE_CAPABILITY_FILE
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                capability = raw.get("capability")
                if isinstance(capability, dict):
                    return dict(capability)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass
        return {
            "provider": "ltx-2.3",
            "gpu_name": "Not yet observed",
            "vram_class_gb": 8,
            "validated_maximum_shot_seconds": self.DEFAULT_HARDWARE_SHOT_LIMIT_SECONDS,
            "governed_maximum_frame_count": 168,
            "provider_maximum_frame_count": 169,
            "validation_status": "conservative-safe-default",
            "source": "phase-20.18.2-safe-default",
        }

    def hardware_shot_limit_seconds(self) -> int:
        """Return the integer governed Shot ceiling used by the current planner."""
        raw = self.hardware_capability().get("validated_maximum_shot_seconds")
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            value = self.DEFAULT_HARDWARE_SHOT_LIMIT_SECONDS
        return max(1, value)

    def propose_hardware_aware_replan(
        self,
        scene_id: str,
    ) -> HardwareAwareShotReplanProposal:
        """Build a replacement plan without mutating current Shot authority."""
        scene = self._require_ready_scene(scene_id)
        source_kind, semantic_source = self._semantic_source_plans(scene)
        proposed = self._semantic_hardware_decomposition(scene, semantic_source)
        capability = self.hardware_capability()
        gpu = str(capability.get("gpu_name") or "Unknown GPU")
        vram = capability.get("vram_class_gb")
        hardware_label = f"{gpu} / {vram} GB" if vram is not None else gpu
        return HardwareAwareShotReplanProposal(
            scene_id=scene.scene_id,
            hardware_label=hardware_label,
            maximum_shot_runtime_seconds=self.hardware_shot_limit_seconds(),
            current_shot_count=len(self.list_plans(scene_id=scene.scene_id)),
            proposed_shot_count=len(proposed),
            scene_runtime_seconds=scene.target_runtime_seconds,
            semantic_source=source_kind,
            semantic_source_shot_count=len(semantic_source),
            proposed_shots=proposed,
        )

    def apply_hardware_aware_replan(
        self,
        scene_id: str,
    ) -> HardwareAwareShotReplanResult:
        """Archive current Shot Plans and replace them with hardware-bounded Draft authority."""
        proposal = self.propose_hardware_aware_replan(scene_id)
        previous = self.list_plans(scene_id=proposal.scene_id)
        archive = self._archive_scene_plans(
            proposal.scene_id,
            previous,
            metadata={
                "hardware_capability": self.hardware_capability(),
                "maximum_shot_runtime_seconds": proposal.maximum_shot_runtime_seconds,
                "replacement_shot_count": proposal.proposed_shot_count,
                "semantic_source": proposal.semantic_source,
                "semantic_source_shot_count": proposal.semantic_source_shot_count,
                "decomposition_strategy": "semantic-hardware-aware-v1",
            },
        )
        remaining = tuple(plan for plan in self.list_plans() if plan.scene_id != proposal.scene_id)
        self._write((*remaining, *proposal.proposed_shots))
        return HardwareAwareShotReplanResult(
            scene_id=proposal.scene_id,
            maximum_shot_runtime_seconds=proposal.maximum_shot_runtime_seconds,
            previous_shot_count=len(previous),
            new_shot_count=len(proposal.proposed_shots),
            archive_path=archive,
            shots=proposal.proposed_shots,
        )

    def list_plans(self, *, scene_id: str | None = None) -> tuple[ShotPlan, ...]:
        """Load Shot Plans in deterministic scene/sequence order."""
        path = self.planning_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            plans = tuple(self._from_dict(item) for item in raw.get("shots", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise GovernedShotPlanningError(f"Unable to load Shot Plans: {exc}") from exc
        if scene_id is not None:
            normalized = scene_id.strip().upper()
            plans = tuple(plan for plan in plans if plan.scene_id == normalized)
        return tuple(
            sorted(
                plans,
                key=lambda plan: (plan.scene_id, plan.sequence_number, plan.shot_id),
            )
        )

    def plan(self, shot_id: str) -> ShotPlan | None:
        """Return one governed Shot Plan by stable identity."""
        normalized = shot_id.strip().upper()
        return next((plan for plan in self.list_plans() if plan.shot_id == normalized), None)

    def legacy_shots_for_scene(self, scene_id: str) -> tuple[ProductionShot, ...]:
        """Return preserved legacy shots not represented by governed Shot Plans."""
        normalized = scene_id.strip().upper()
        governed_ids = {plan.shot_id for plan in self.list_plans(scene_id=normalized)}
        return tuple(
            shot
            for shot in self.legacy_shots.list_shots(normalized)
            if shot.shot_id.strip().upper() not in governed_ids
        )

    def next_sequence_number(self, scene_id: str) -> int:
        """Return the next governed shot sequence number for a Scene."""
        return (
            max(
                (plan.sequence_number for plan in self.list_plans(scene_id=scene_id)),
                default=0,
            )
            + 1
        )

    def allocated_runtime_seconds(self, scene_id: str) -> int:
        """Return governed shot runtime allocated within one Scene."""
        return sum(plan.target_runtime_seconds for plan in self.list_plans(scene_id=scene_id))

    def remaining_runtime_seconds(self, scene_id: str) -> int:
        """Return unallocated Scene runtime, never below zero."""
        scene = self._require_scene(scene_id)
        return max(0, scene.target_runtime_seconds - self.allocated_runtime_seconds(scene_id))

    def effective_constraints(self, shot: ShotPlan) -> tuple[str, ...]:
        """Return inherited Scene constraints followed by shot-specific constraints."""
        scene = self._require_scene(shot.scene_id)
        return self._values((*scene.scene_constraints, *shot.shot_constraints))

    def is_upstream_current(self, shot: ShotPlan) -> bool:
        """Return whether the Shot Plan still matches its authoritative Scene contract."""
        scene = self.scenes.plan(shot.scene_id)
        return scene is not None and shot.scene_contract_hash == self._scene_contract_hash(scene)

    def is_production_ready(self, shot: ShotPlan) -> bool:
        """Return whether specialist planners may safely consume this Shot Plan."""
        scene = self.scenes.plan(shot.scene_id)
        return (
            shot.status is ShotPlanStatus.READY
            and scene is not None
            and self.scenes.is_production_ready(scene)
            and self.is_upstream_current(shot)
        )

    def create(
        self,
        *,
        scene_id: str,
        sequence_number: int,
        title: str,
        narrative_purpose: str,
        production_objective: str,
        target_runtime_seconds: int,
        required_action: str,
        dialogue_requirement: str = "",
        continuity_in: str = "",
        continuity_out: str = "",
        shot_constraints: tuple[str, ...] = (),
    ) -> ShotPlan:
        """Create a Draft Shot Plan beneath one authoritative Ready Scene Plan."""
        scene = self._require_ready_scene(scene_id)
        if sequence_number < 1:
            raise GovernedShotPlanningError("Shot sequence number must be at least 1")
        shot_id = self._shot_id(scene.scene_id, sequence_number)
        if self.plan(shot_id) is not None:
            raise GovernedShotPlanningError(f"Shot Plan already exists: {shot_id}")
        runtime = self._runtime(target_runtime_seconds)
        self._validate_runtime_budget(scene, runtime)
        plan = ShotPlan(
            shot_id=shot_id,
            scene_id=scene.scene_id,
            sequence_number=sequence_number,
            title=self._required(title, "Shot title"),
            narrative_purpose=self._required(narrative_purpose, "Narrative purpose"),
            production_objective=self._required(production_objective, "Production objective"),
            target_runtime_seconds=runtime,
            required_action=self._required(required_action, "Required action"),
            dialogue_requirement=dialogue_requirement.strip(),
            continuity_in=continuity_in.strip(),
            continuity_out=continuity_out.strip(),
            shot_constraints=self._values(shot_constraints),
            scene_contract_hash=self._scene_contract_hash(scene),
        )
        self._write((*self.list_plans(), plan))
        return plan

    def update(
        self,
        shot_id: str,
        *,
        title: str,
        narrative_purpose: str,
        production_objective: str,
        target_runtime_seconds: int,
        required_action: str,
        dialogue_requirement: str,
        continuity_in: str,
        continuity_out: str,
        shot_constraints: tuple[str, ...],
    ) -> ShotPlan:
        """Update an editable Draft Shot Plan and refresh its Scene fingerprint."""
        current = self._require_plan(shot_id)
        if current.status is not ShotPlanStatus.DRAFT:
            raise GovernedShotPlanningError("Ready Shot Plans must return to Draft before editing")
        scene = self._require_ready_scene(current.scene_id)
        runtime = self._runtime(target_runtime_seconds)
        self._validate_runtime_budget(scene, runtime, excluding_shot_id=current.shot_id)
        updated = replace(
            current,
            title=self._required(title, "Shot title"),
            narrative_purpose=self._required(narrative_purpose, "Narrative purpose"),
            production_objective=self._required(production_objective, "Production objective"),
            target_runtime_seconds=runtime,
            required_action=self._required(required_action, "Required action"),
            dialogue_requirement=dialogue_requirement.strip(),
            continuity_in=continuity_in.strip(),
            continuity_out=continuity_out.strip(),
            shot_constraints=self._values(shot_constraints),
            scene_contract_hash=self._scene_contract_hash(scene),
        )
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> ShotPlan:
        """Make a current Shot Plan available to specialist planners."""
        current = self._require_plan(shot_id)
        if current.status is ShotPlanStatus.READY:
            return current
        scene = self._require_ready_scene(current.scene_id)
        if current.scene_contract_hash != self._scene_contract_hash(scene):
            raise GovernedShotPlanningError(
                "Shot Plan is stale because the Scene contract changed; edit and save it before marking Ready"
            )
        self._validate_ready(current)
        updated = replace(current, status=ShotPlanStatus.READY)
        self._replace(updated)
        return updated

    def return_to_draft(self, shot_id: str) -> ShotPlan:
        """Return a Ready Shot Plan to editable Draft state."""
        current = self._require_plan(shot_id)
        updated = replace(current, status=ShotPlanStatus.DRAFT)
        self._replace(updated)
        return updated

    def delete(self, shot_id: str) -> bool:
        """Delete only a Draft governed Shot Plan."""
        current = self.plan(shot_id)
        if current is None:
            return False
        if current.status is not ShotPlanStatus.DRAFT:
            raise GovernedShotPlanningError("Ready Shot Plans must return to Draft before deletion")
        remaining = tuple(plan for plan in self.list_plans() if plan.shot_id != current.shot_id)
        self._write(remaining)
        return True

    def _semantic_source_plans(
        self,
        scene: ScenePlan,
    ) -> tuple[str, tuple[ShotPlan, ...]]:
        """Choose the richest preserved semantic Shot authority for hardware decomposition."""
        candidates: list[tuple[str, tuple[ShotPlan, ...]]] = []
        current = self.list_plans(scene_id=scene.scene_id)
        if current:
            candidates.append(("current-governed-plan", current))
        candidates.extend(self._archived_scene_plan_candidates(scene.scene_id))

        valid = [
            (source, plans)
            for source, plans in candidates
            if plans
            and sum(plan.target_runtime_seconds for plan in plans)
            == scene.target_runtime_seconds
        ]
        if not valid:
            return ("scene-authority-fallback", self._scene_semantic_fallback(scene))

        return max(
            valid,
            key=lambda item: (
                self._semantic_density(item[1]),
                -len(item[1]),
            ),
        )

    def _archived_scene_plan_candidates(
        self,
        scene_id: str,
    ) -> tuple[tuple[str, tuple[ShotPlan, ...]], ...]:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        safe_scene_id = scene_id.replace("/", "-").replace("\\", "-")
        directory = (
            self.projects.project_directory
            / "planning"
            / self.HISTORY_DIRECTORY
            / safe_scene_id
        )
        if not directory.is_dir():
            return ()

        candidates: list[tuple[str, tuple[ShotPlan, ...]]] = []
        for path in sorted(directory.glob("*.json"), reverse=True):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                shots = raw.get("shots", [])
                if not isinstance(shots, list):
                    continue
                plans = tuple(
                    self._from_dict(item)
                    for item in shots
                    if isinstance(item, dict)
                )
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if plans:
                candidates.append((f"archived:{path.name}", plans))
        return tuple(candidates)

    @staticmethod
    def _semantic_density(plans: tuple[ShotPlan, ...]) -> float:
        """Score narrative specificity while strongly penalising generic generated beat labels."""
        if not plans:
            return 0.0
        generic_titles = 0
        substantive_titles: set[str] = set()
        purposes: set[str] = set()
        actions: set[str] = set()
        dialogue = 0
        for plan in plans:
            title = plan.title.strip()
            lowered = title.casefold()
            if (
                lowered.startswith("story beat ")
                or lowered.startswith("establish —")
                or lowered.startswith("close —")
            ):
                generic_titles += 1
            else:
                substantive_titles.add(lowered)
            purposes.add(plan.narrative_purpose.strip().casefold())
            actions.add(plan.required_action.strip().casefold())
            dialogue += int(bool(plan.dialogue_requirement.strip()))
        score = (
            len(substantive_titles) * 5
            + len(purposes) * 2
            + len(actions) * 2
            + dialogue
            - generic_titles * 3
        )
        return score / len(plans)

    def _scene_semantic_fallback(self, scene: ScenePlan) -> tuple[ShotPlan, ...]:
        """Build semantic beats only when no complete governed or archived Shot authority exists."""
        events = scene.required_events or (scene.production_objective,)
        event_count = len(events)
        base, remainder = divmod(scene.target_runtime_seconds, event_count)
        scene_hash = self._scene_contract_hash(scene)
        return tuple(
            ShotPlan(
                shot_id=self._shot_id(scene.scene_id, index),
                scene_id=scene.scene_id,
                sequence_number=index,
                title=f"{scene.title} — {event[:48]}",
                narrative_purpose=f"Advance the Scene through the required event: {event}",
                production_objective=scene.production_objective,
                target_runtime_seconds=base + (1 if index <= remainder else 0),
                required_action=f"Present the required story event: {event}",
                continuity_in=(
                    scene.continuity_in
                    if index == 1
                    else f"Continue from semantic beat {index - 1}."
                ),
                continuity_out=(
                    scene.continuity_out
                    if index == event_count
                    else f"Continue into semantic beat {index + 1}."
                ),
                scene_contract_hash=scene_hash,
                status=ShotPlanStatus.DRAFT,
            )
            for index, event in enumerate(events, start=1)
        )

    def _semantic_hardware_decomposition(
        self,
        scene: ScenePlan,
        semantic_source: tuple[ShotPlan, ...],
    ) -> tuple[ShotPlan, ...]:
        """Split each semantic Shot beat into intentional short editorial Shots."""
        limit = self.hardware_shot_limit_seconds()
        scene_hash = self._scene_contract_hash(scene)
        output: list[ShotPlan] = []
        sequence = 1
        for source in semantic_source:
            piece_count = max(1, ceil(source.target_runtime_seconds / limit))
            base, remainder = divmod(source.target_runtime_seconds, piece_count)
            runtimes = tuple(
                base + (1 if index < remainder else 0)
                for index in range(piece_count)
            )
            if any(runtime <= 0 or runtime > limit for runtime in runtimes):
                raise GovernedShotPlanningError(
                    f"Unable to decompose semantic Shot {source.shot_id} within "
                    f"the active {limit}s hardware limit"
                )

            for piece_index, runtime in enumerate(runtimes, start=1):
                shot_id = self._shot_id(scene.scene_id, sequence)
                previous_id = (
                    self._shot_id(scene.scene_id, sequence - 1)
                    if sequence > 1
                    else None
                )
                next_id = self._shot_id(scene.scene_id, sequence + 1)
                output.append(
                    ShotPlan(
                        shot_id=shot_id,
                        scene_id=scene.scene_id,
                        sequence_number=sequence,
                        title=self._decomposed_title(
                            source.title,
                            piece_index,
                            piece_count,
                        ),
                        narrative_purpose=self._decomposed_purpose(
                            source.narrative_purpose,
                            piece_index,
                            piece_count,
                        ),
                        production_objective=source.production_objective,
                        target_runtime_seconds=runtime,
                        required_action=self._decomposed_action(
                            source.required_action,
                            piece_index,
                            piece_count,
                        ),
                        dialogue_requirement=(
                            source.dialogue_requirement
                            if self._dialogue_piece(piece_index, piece_count)
                            else ""
                        ),
                        continuity_in=(
                            source.continuity_in
                            if piece_index == 1
                            else f"Continue directly from {previous_id}."
                        ),
                        continuity_out=(
                            source.continuity_out
                            if piece_index == piece_count
                            else f"Continue into {next_id}."
                        ),
                        shot_constraints=self._values(
                            (
                                *source.shot_constraints,
                                (
                                    f"Hardware-aware Shot runtime must not exceed "
                                    f"{limit} seconds."
                                ),
                                (
                                    f"Preserve semantic source Shot {source.shot_id}: "
                                    f"{source.title}."
                                ),
                            )
                        ),
                        scene_contract_hash=scene_hash,
                        status=ShotPlanStatus.DRAFT,
                    )
                )
                sequence += 1

        total = sum(plan.target_runtime_seconds for plan in output)
        if total != scene.target_runtime_seconds:
            raise GovernedShotPlanningError(
                f"Semantic hardware decomposition produced {total}s but Scene authority "
                f"requires {scene.target_runtime_seconds}s"
            )
        return tuple(output)

    @staticmethod
    def _decomposed_title(title: str, index: int, count: int) -> str:
        if count == 1:
            return title
        if index == 1:
            suffix = "Establish"
        elif index == count:
            suffix = "Resolve"
        else:
            coverage = ("Detail", "Reaction", "Coverage", "Progression", "Response")
            suffix = coverage[(index - 2) % len(coverage)]
        return f"{title} — {suffix}"

    @staticmethod
    def _decomposed_purpose(purpose: str, index: int, count: int) -> str:
        if count == 1:
            return purpose
        if index == 1:
            return f"Establish the semantic beat: {purpose}"
        if index == count:
            return f"Resolve the semantic beat: {purpose}"
        return f"Advance the semantic beat with distinct editorial coverage: {purpose}"

    @staticmethod
    def _decomposed_action(action: str, index: int, count: int) -> str:
        if count == 1:
            return action
        if index == 1:
            return f"Begin the beat action: {action}"
        if index == count:
            return f"Complete the beat action: {action}"
        return f"Continue the beat action from a distinct cinematic angle: {action}"

    @staticmethod
    def _dialogue_piece(index: int, count: int) -> bool:
        if count <= 1:
            return True
        return index == min(2, count)

    def _archive_scene_plans(
        self,
        scene_id: str,
        plans: tuple[ShotPlan, ...],
        *,
        metadata: dict[str, Any],
    ) -> Path | None:
        if not plans:
            return None
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        safe_scene_id = scene_id.replace("/", "-").replace("\\", "-")
        directory = (
            self.projects.project_directory / "planning" / self.HISTORY_DIRECTORY / safe_scene_id
        )
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        path = directory / f"{timestamp}.json"
        payload = {
            "schema_version": "1.0",
            "scene_id": scene_id,
            "archived_at": datetime.now(UTC).isoformat(),
            "reason": "hardware-aware-scene-replan",
            "metadata": metadata,
            "shots": [self._to_dict(plan) for plan in plans],
        }
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def reorder_scene(
        self,
        scene_id: str,
        ordered_shot_ids: tuple[str, ...],
    ) -> tuple[ShotPlan, ...]:
        """Persist explicit governed Shot Plan order within one Scene."""
        current = self.list_plans(scene_id=scene_id)
        by_id = {plan.shot_id: plan for plan in current}
        if len(ordered_shot_ids) != len(by_id) or set(ordered_shot_ids) != set(by_id):
            raise GovernedShotPlanningError(
                "Reorder must include every governed Shot Plan in the Scene exactly once"
            )
        replacements = {
            shot_id: replace(by_id[shot_id], sequence_number=index)
            for index, shot_id in enumerate(ordered_shot_ids, start=1)
        }
        all_plans = tuple(replacements.get(plan.shot_id, plan) for plan in self.list_plans())
        self._write(all_plans)
        return self.list_plans(scene_id=scene_id)

    def _validate_ready(self, shot: ShotPlan) -> None:
        self._required(shot.title, "Shot title")
        self._required(shot.narrative_purpose, "Narrative purpose")
        self._required(shot.production_objective, "Production objective")
        self._required(shot.required_action, "Required action")
        self._runtime(shot.target_runtime_seconds)

    def _validate_runtime_budget(
        self,
        scene: ScenePlan,
        proposed_runtime: int,
        *,
        excluding_shot_id: str | None = None,
    ) -> None:
        allocated = sum(
            plan.target_runtime_seconds
            for plan in self.list_plans(scene_id=scene.scene_id)
            if plan.shot_id != excluding_shot_id
        )
        if allocated + proposed_runtime > scene.target_runtime_seconds:
            remaining = max(0, scene.target_runtime_seconds - allocated)
            raise GovernedShotPlanningError(
                "Shot runtime exceeds the Scene budget "
                f"({remaining} seconds remain of {scene.target_runtime_seconds})"
            )

    def _require_ready_scene(self, scene_id: str) -> ScenePlan:
        scene = self._require_scene(scene_id)
        if scene.status is not ScenePlanStatus.READY or not self.scenes.is_production_ready(scene):
            raise GovernedShotPlanningError("Shot Planning requires a current Ready Scene Plan")
        return scene

    def _require_scene(self, scene_id: str) -> ScenePlan:
        scene = self.scenes.plan(scene_id)
        if scene is None:
            raise GovernedShotPlanningError(f"Scene Plan not found: {scene_id}")
        return scene

    def _require_plan(self, shot_id: str) -> ShotPlan:
        shot = self.plan(shot_id)
        if shot is None:
            raise GovernedShotPlanningError(f"Shot Plan not found: {shot_id}")
        return shot

    def _replace(self, updated: ShotPlan) -> None:
        plans = tuple(
            updated if plan.shot_id == updated.shot_id else plan for plan in self.list_plans()
        )
        self._write(plans)

    def _write(self, plans: tuple[ShotPlan, ...]) -> None:
        path = self.planning_file
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(
            plans,
            key=lambda plan: (plan.scene_id, plan.sequence_number, plan.shot_id),
        )
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "shots": [self._to_dict(plan) for plan in ordered],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise GovernedShotPlanningError(f"Unable to save Shot Plans: {exc}") from exc

    @staticmethod
    def _to_dict(plan: ShotPlan) -> dict[str, Any]:
        raw = asdict(plan)
        raw["status"] = plan.status.value
        raw["shot_constraints"] = list(plan.shot_constraints)
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> ShotPlan:
        return ShotPlan(
            shot_id=str(raw["shot_id"]).strip().upper(),
            scene_id=str(raw["scene_id"]).strip().upper(),
            sequence_number=int(raw["sequence_number"]),
            title=str(raw["title"]),
            narrative_purpose=str(raw["narrative_purpose"]),
            production_objective=str(raw["production_objective"]),
            target_runtime_seconds=int(raw["target_runtime_seconds"]),
            required_action=str(raw["required_action"]),
            dialogue_requirement=str(raw.get("dialogue_requirement", "")),
            continuity_in=str(raw.get("continuity_in", "")),
            continuity_out=str(raw.get("continuity_out", "")),
            shot_constraints=tuple(str(value) for value in raw.get("shot_constraints", [])),
            scene_contract_hash=str(raw.get("scene_contract_hash", "")),
            status=ShotPlanStatus(str(raw.get("status", ShotPlanStatus.DRAFT.value))),
        )

    @classmethod
    def _scene_contract_hash(cls, scene: ScenePlan) -> str:
        payload = {
            "scene_id": scene.scene_id,
            "episode_id": scene.episode_id,
            "sequence_number": scene.sequence_number,
            "title": scene.title,
            "story_scope": scene.story_scope,
            "production_objective": scene.production_objective,
            "target_runtime_seconds": scene.target_runtime_seconds,
            "setting_requirement": scene.setting_requirement,
            "required_events": list(scene.required_events),
            "continuity_in": scene.continuity_in,
            "continuity_out": scene.continuity_out,
            "scene_constraints": list(scene.scene_constraints),
        }
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _shot_id(scene_id: str, sequence_number: int) -> str:
        return f"{scene_id}-SHT-{sequence_number:03d}"

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise GovernedShotPlanningError(f"{label} is required")
        return normalized

    @staticmethod
    def _runtime(value: int) -> int:
        if value <= 0:
            raise GovernedShotPlanningError("Target runtime must be greater than zero")
        return value

    @staticmethod
    def _values(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
