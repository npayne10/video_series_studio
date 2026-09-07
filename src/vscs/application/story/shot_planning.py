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
    proposed_shots: tuple["ShotPlan", ...]


@dataclass(frozen=True, slots=True)
class HardwareAwareShotReplanResult:
    """Durable result after a human-approved hardware-aware Scene replan."""

    scene_id: str
    maximum_shot_runtime_seconds: int
    previous_shot_count: int
    new_shot_count: int
    archive_path: Path | None
    shots: tuple["ShotPlan", ...]


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
    HARDWARE_CAPABILITY_FILE = (
        Path(".vscs") / "provider_executions" / "hardware_capability.json"
    )

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
        proposed = self._hardware_aware_shots(scene)
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
            },
        )
        remaining = tuple(
            plan for plan in self.list_plans() if plan.scene_id != proposal.scene_id
        )
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

    def _hardware_aware_shots(self, scene: ScenePlan) -> tuple[ShotPlan, ...]:
        limit = self.hardware_shot_limit_seconds()
        shot_count = max(1, ceil(scene.target_runtime_seconds / limit))
        base, remainder = divmod(scene.target_runtime_seconds, shot_count)
        runtimes = tuple(
            base + (1 if index < remainder else 0)
            for index in range(shot_count)
        )
        if any(runtime > limit or runtime <= 0 for runtime in runtimes):
            raise GovernedShotPlanningError(
                "Unable to distribute Scene runtime within the active hardware Shot limit"
            )

        events = scene.required_events or (scene.production_objective,)
        scene_hash = self._scene_contract_hash(scene)
        plans: list[ShotPlan] = []
        for index, runtime in enumerate(runtimes, start=1):
            event = events[(index - 1) % len(events)]
            if index == 1:
                title = f"Establish — {scene.title}"
                purpose = (
                    f"Establish {scene.setting_requirement} and orient the audience to "
                    f"{scene.story_scope}"
                )
                action = f"Establish the scene state before progressing into: {event}"
                continuity_in = scene.continuity_in
            elif index == shot_count:
                title = f"Close — {scene.title}"
                purpose = (
                    f"Complete the scene objective and prepare the editorial transition: "
                    f"{scene.production_objective}"
                )
                action = f"Resolve the final required story beat: {event}"
                continuity_in = f"Continue directly from {self._shot_id(scene.scene_id, index - 1)}."
            else:
                title = f"Story Beat {index:03d}"
                purpose = f"Advance the ordered Scene story through: {event}"
                action = (
                    f"Show the required story event as a distinct cinematic beat: {event}"
                )
                continuity_in = f"Continue directly from {self._shot_id(scene.scene_id, index - 1)}."

            continuity_out = (
                scene.continuity_out
                if index == shot_count
                else f"Continue into {self._shot_id(scene.scene_id, index + 1)}."
            )
            plans.append(
                ShotPlan(
                    shot_id=self._shot_id(scene.scene_id, index),
                    scene_id=scene.scene_id,
                    sequence_number=index,
                    title=title,
                    narrative_purpose=purpose,
                    production_objective=scene.production_objective,
                    target_runtime_seconds=runtime,
                    required_action=action,
                    dialogue_requirement="",
                    continuity_in=continuity_in,
                    continuity_out=continuity_out,
                    shot_constraints=(
                        f"Hardware-aware Shot runtime must not exceed {limit} seconds.",
                    ),
                    scene_contract_hash=scene_hash,
                    status=ShotPlanStatus.DRAFT,
                )
            )
        return tuple(plans)

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
            self.projects.project_directory
            / "planning"
            / self.HISTORY_DIRECTORY
            / safe_scene_id
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

    def _runtime(self, value: int) -> int:
        if value <= 0:
            raise GovernedShotPlanningError("Target runtime must be greater than zero")
        limit = self.hardware_shot_limit_seconds()
        if value > limit:
            raise GovernedShotPlanningError(
                f"Target runtime {value}s exceeds the active hardware-aware Shot limit "
                f"of {limit}s. Re-plan the Scene or shorten the Shot."
            )
        return value

    @staticmethod
    def _values(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
