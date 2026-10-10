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
class ShotReplanProtection:
    """One current Shot that cannot be replaced because downstream production exists."""

    shot_id: str
    reasons: tuple[str, ...]


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
    protected_shots: tuple[ShotReplanProtection, ...] = ()
    regenerated_shot_count: int = 0


@dataclass(frozen=True, slots=True)
class HardwareAwareShotReplanResult:
    """Durable result after a human-approved hardware-aware Scene replan."""

    scene_id: str
    maximum_shot_runtime_seconds: int
    previous_shot_count: int
    new_shot_count: int
    archive_path: Path | None
    shots: tuple[ShotPlan, ...]


class CinematicCoverageRole(StrEnum):
    """Editorial role assigned to a hardware-decomposed governed Shot."""

    UNSPECIFIED = "unspecified"
    ESTABLISHING = "establishing"
    PRIMARY_SUBJECT = "primary_subject"
    SECONDARY_SUBJECT = "secondary_subject"
    DETAIL_INSERT = "detail_insert"
    DIALOGUE_DELIVERY = "dialogue_delivery"
    REACTION = "reaction"
    PROGRESSION = "progression"
    RESOLVE = "resolve"


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
    coverage_role: CinematicCoverageRole = CinematicCoverageRole.UNSPECIFIED
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
    DEFAULT_GOVERNED_SHOT_LIMIT_SECONDS = 15
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

    def governed_shot_limit_seconds(self) -> int:
        """Return the provider-neutral cinematic Shot ceiling used by planning."""
        return max(1, self.DEFAULT_GOVERNED_SHOT_LIMIT_SECONDS)

    def hardware_shot_limit_seconds(self) -> int:
        """Backward-compatible alias for the governed cinematic Shot ceiling."""
        return self.governed_shot_limit_seconds()

    def propose_hardware_aware_replan(
        self,
        scene_id: str,
    ) -> HardwareAwareShotReplanProposal:
        """Build a cinematic replacement plan without mutating current Shot authority."""
        scene = self._require_ready_scene(scene_id)
        current = self.list_plans(scene_id=scene.scene_id)
        protections = self._production_replan_protections(current)
        protected = self._protected_produced_prefix(
            current=current,
            protections=protections,
        )
        source_kind, semantic_source = self._semantic_source_plans(scene)

        protected_runtime = sum(plan.target_runtime_seconds for plan in protected)
        if protected_runtime > scene.target_runtime_seconds:
            raise GovernedShotPlanningError(
                "Produced Shot prefix exceeds the authoritative Scene runtime; "
                "automatic replanning is blocked."
            )

        semantic_suffix = self._semantic_suffix_after_protected_prefix(
            semantic_source=semantic_source,
            protected=protected,
            protected_runtime_seconds=protected_runtime,
        )
        regenerated = self._semantic_hardware_decomposition(
            scene,
            semantic_suffix,
            sequence_start=len(protected) + 1,
            expected_runtime_seconds=scene.target_runtime_seconds - protected_runtime,
        )
        proposed = (*protected, *regenerated)

        total = sum(plan.target_runtime_seconds for plan in proposed)
        if total != scene.target_runtime_seconds:
            raise GovernedShotPlanningError(
                f"Production-aware Scene replan produced {total}s but Scene authority "
                f"requires {scene.target_runtime_seconds}s"
            )

        capability = self.hardware_capability()
        gpu = str(capability.get("gpu_name") or "Unknown GPU")
        vram = capability.get("vram_class_gb")
        hardware_label = f"{gpu} / {vram} GB" if vram is not None else gpu
        return HardwareAwareShotReplanProposal(
            scene_id=scene.scene_id,
            hardware_label=hardware_label,
            maximum_shot_runtime_seconds=self.governed_shot_limit_seconds(),
            current_shot_count=len(current),
            proposed_shot_count=len(proposed),
            scene_runtime_seconds=scene.target_runtime_seconds,
            semantic_source=source_kind,
            semantic_source_shot_count=len(semantic_source),
            proposed_shots=proposed,
            protected_shots=protections,
            regenerated_shot_count=len(regenerated),
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
                "decomposition_strategy": "semantic-cinematic-coverage-v1",
                "protected_shot_ids": [item.shot_id for item in proposal.protected_shots],
                "protected_shot_reasons": {
                    item.shot_id: list(item.reasons) for item in proposal.protected_shots
                },
                "regenerated_shot_count": proposal.regenerated_shot_count,
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

    def _production_replan_protections(
        self,
        plans: tuple[ShotPlan, ...],
    ) -> tuple[ShotReplanProtection, ...]:
        """Protect Shots with durable downstream production evidence from automatic replacement."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        project = self.projects.project_directory
        reasons_by_shot: dict[str, list[str]] = {plan.shot_id: [] for plan in plans}

        boundary_path = project / ".vscs" / "governed_shot_boundaries.json"
        if boundary_path.is_file():
            root = self._read_replan_evidence(boundary_path, "governed Shot boundary")
            boundaries = root.get("boundaries", [])
            if not isinstance(boundaries, list):
                raise GovernedShotPlanningError(
                    "Governed Shot boundary evidence is invalid; automatic replanning is blocked"
                )
            for item in boundaries:
                if not isinstance(item, dict):
                    continue
                shot_id = str(item.get("shot_id") or "").strip().upper()
                status = str(item.get("status") or "").strip().casefold()
                if shot_id in reasons_by_shot and status == "published":
                    reasons_by_shot[shot_id].append("published governed closing boundary")

        acceptance_path = project / ".vscs" / "timed_span_acceptance.json"
        if acceptance_path.is_file():
            root = self._read_replan_evidence(acceptance_path, "timed-span acceptance")
            assemblies = root.get("assemblies", [])
            if not isinstance(assemblies, list):
                raise GovernedShotPlanningError(
                    "Timed-span assembly evidence is invalid; automatic replanning is blocked"
                )
            for item in assemblies:
                if not isinstance(item, dict):
                    continue
                shot_id = str(item.get("shot_id") or "").strip().upper()
                if shot_id in reasons_by_shot:
                    reasons_by_shot[shot_id].append("verified governed span assembly")

        adoption_path = (
            project / ".vscs" / "production_execution" / "provider_production_adoptions.json"
        )
        if adoption_path.is_file():
            root = self._read_replan_evidence(adoption_path, "provider production adoption")
            records = root.get("records", [])
            if not isinstance(records, list):
                raise GovernedShotPlanningError(
                    "Provider production adoption evidence is invalid; automatic replanning is blocked"
                )
            for item in records:
                if not isinstance(item, dict):
                    continue
                shot_id = str(item.get("shot_id") or "").strip().upper()
                state = str(item.get("state") or "").strip().casefold()
                if shot_id in reasons_by_shot and state:
                    reasons_by_shot[shot_id].append(f"provider production adoption: {state}")

        return tuple(
            ShotReplanProtection(
                shot_id=plan.shot_id,
                reasons=tuple(dict.fromkeys(reasons_by_shot[plan.shot_id])),
            )
            for plan in plans
            if reasons_by_shot[plan.shot_id]
        )

    @staticmethod
    def _read_replan_evidence(path: Path, label: str) -> dict[str, Any]:
        try:
            root = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GovernedShotPlanningError(
                f"Unable to read {label} evidence; automatic replanning is blocked: {exc}"
            ) from exc
        if not isinstance(root, dict):
            raise GovernedShotPlanningError(
                f"{label.title()} evidence is invalid; automatic replanning is blocked"
            )
        return root

    @staticmethod
    def _protected_produced_prefix(
        *,
        current: tuple[ShotPlan, ...],
        protections: tuple[ShotReplanProtection, ...],
    ) -> tuple[ShotPlan, ...]:
        """Return only a contiguous produced prefix; never regenerate it for comparison."""
        if not protections:
            return ()
        protected_ids = tuple(item.shot_id for item in protections)
        expected_prefix = tuple(plan.shot_id for plan in current[: len(protected_ids)])
        if protected_ids != expected_prefix:
            raise GovernedShotPlanningError(
                "Automatic Scene replanning is blocked because produced Shots do not form "
                "a contiguous prefix. Use an explicit supersession workflow instead."
            )
        return current[: len(protections)]

    def _semantic_suffix_after_protected_prefix(
        self,
        *,
        semantic_source: tuple[ShotPlan, ...],
        protected: tuple[ShotPlan, ...],
        protected_runtime_seconds: int,
    ) -> tuple[ShotPlan, ...]:
        """Trim semantic authority at the produced temporal boundary and return future authority."""
        if protected_runtime_seconds <= 0:
            return semantic_source

        semantic_total = sum(plan.target_runtime_seconds for plan in semantic_source)
        if protected_runtime_seconds >= semantic_total:
            if protected_runtime_seconds == semantic_total:
                return ()
            raise GovernedShotPlanningError(
                "Produced Shot prefix extends beyond recovered semantic authority; "
                "automatic replanning is blocked."
            )

        remaining_to_consume = protected_runtime_seconds
        semantic_cursor = 0
        suffix: list[ShotPlan] = []
        last_protected_id = protected[-1].shot_id if protected else ""

        for source in semantic_source:
            source_start = semantic_cursor
            source_end = source_start + source.target_runtime_seconds
            semantic_cursor = source_end

            if remaining_to_consume >= source.target_runtime_seconds:
                remaining_to_consume -= source.target_runtime_seconds
                continue

            if remaining_to_consume > 0:
                consumed_into_source = remaining_to_consume
                residual_runtime = source.target_runtime_seconds - consumed_into_source
                consumed_dialogue = self._protected_dialogue_overlaps(
                    protected,
                    source_start=source_start,
                    consumed_through=source_start + consumed_into_source,
                )
                dialogue_requirement = source.dialogue_requirement
                required_action = source.required_action
                if consumed_dialogue and dialogue_requirement.strip():
                    dialogue_requirement = ""
                    required_action = (
                        "Continue the observable non-dialogue physical state of the semantic beat: "
                        f"{source.narrative_purpose}"
                    )
                suffix.append(
                    replace(
                        source,
                        target_runtime_seconds=residual_runtime,
                        required_action=required_action,
                        dialogue_requirement=dialogue_requirement,
                        continuity_in=(
                            f"Continue directly from {last_protected_id}."
                            if last_protected_id
                            else source.continuity_in
                        ),
                    )
                )
                remaining_to_consume = 0
                continue

            suffix.append(source)

        if remaining_to_consume != 0:
            raise GovernedShotPlanningError(
                "Produced Shot prefix cannot be aligned to recovered semantic authority; "
                "automatic replanning is blocked."
            )
        return tuple(suffix)

    @staticmethod
    def _protected_dialogue_overlaps(
        protected: tuple[ShotPlan, ...],
        *,
        source_start: int,
        consumed_through: int,
    ) -> bool:
        cursor = 0
        for shot in protected:
            shot_start = cursor
            shot_end = shot_start + shot.target_runtime_seconds
            cursor = shot_end
            if shot_end <= source_start or shot_start >= consumed_through:
                continue
            if shot.dialogue_requirement.strip():
                return True
        return False

    def _semantic_source_plans(
        self,
        scene: ScenePlan,
    ) -> tuple[str, tuple[ShotPlan, ...]]:
        """Select current semantic authority before considering historical recovery data."""
        current = self.list_plans(scene_id=scene.scene_id)
        if self._is_complete_semantic_source(scene, current):
            lineage_markers = self._hardware_lineage_markers(current)
            if lineage_markers:
                lineage = self._matching_hardware_lineage_archive(scene, current)
                if lineage is not None:
                    return lineage
                raise GovernedShotPlanningError(
                    "Hardware-derived Shot lineage is present but its semantic source archive "
                    "cannot be recovered; automatic replanning is blocked."
                )
            return ("current-governed-plan", current)

        for source, plans in self._archived_scene_plan_candidates(scene.scene_id):
            if self._is_complete_semantic_source(scene, plans):
                return (source, plans)

        return ("scene-authority-fallback", self._scene_semantic_fallback(scene))

    def _matching_hardware_lineage_archive(
        self,
        scene: ScenePlan,
        current: tuple[ShotPlan, ...],
    ) -> tuple[str, tuple[ShotPlan, ...]] | None:
        """Recover only an archive explicitly named by current hardware-derived Shots."""
        lineage = self._hardware_lineage_markers(current)
        if not lineage:
            return None

        for source, plans in self._archived_scene_plan_candidates(scene.scene_id):
            if not self._is_complete_semantic_source(scene, plans):
                continue
            expected = frozenset(self._semantic_source_marker(plan) for plan in plans)
            if expected == lineage:
                return (source, plans)
        return None

    def _is_complete_semantic_source(
        self,
        scene: ScenePlan,
        plans: tuple[ShotPlan, ...],
    ) -> bool:
        """Return whether a plan is current, complete, and semantically usable."""
        if not plans:
            return False
        if sum(plan.target_runtime_seconds for plan in plans) != scene.target_runtime_seconds:
            return False
        scene_hash = self._scene_contract_hash(scene)
        for plan in plans:
            if plan.scene_id != scene.scene_id or plan.scene_contract_hash != scene_hash:
                return False
            if plan.target_runtime_seconds <= 0:
                return False
            if not all(
                value.strip()
                for value in (
                    plan.title,
                    plan.narrative_purpose,
                    plan.production_objective,
                    plan.required_action,
                )
            ):
                return False
        return self._semantic_density(plans) > 0.0

    def _hardware_lineage_markers(
        self,
        plans: tuple[ShotPlan, ...],
    ) -> frozenset[str]:
        """Return semantic-parent markers proven by intact hardware-derived Shots."""
        markers: set[str] = set()
        prefix = "Preserve semantic source Shot "
        for plan in plans:
            if plan.coverage_role is CinematicCoverageRole.UNSPECIFIED:
                continue
            role_constraint = f"Cinematic coverage role: {plan.coverage_role.value}."
            if role_constraint not in plan.shot_constraints:
                continue
            if not plan.title.endswith(f"— {self._coverage_label(plan.coverage_role)}"):
                continue
            marker = next(
                (
                    constraint
                    for constraint in reversed(plan.shot_constraints)
                    if constraint.startswith(prefix)
                ),
                None,
            )
            if marker is None:
                continue
            markers.add(marker)
        return frozenset(markers)

    @staticmethod
    def _semantic_source_marker(plan: ShotPlan) -> str:
        return f"Preserve semantic source Shot {plan.shot_id}: {plan.title}."

    def _archived_scene_plan_candidates(
        self,
        scene_id: str,
    ) -> tuple[tuple[str, tuple[ShotPlan, ...]], ...]:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        safe_scene_id = scene_id.replace("/", "-").replace("\\", "-")
        directory = (
            self.projects.project_directory / "planning" / self.HISTORY_DIRECTORY / safe_scene_id
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
                plans = tuple(self._from_dict(item) for item in shots if isinstance(item, dict))
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
        *,
        sequence_start: int = 1,
        expected_runtime_seconds: int | None = None,
    ) -> tuple[ShotPlan, ...]:
        """Split semantic authority into provider-neutral cinematic Shots."""
        limit = self.governed_shot_limit_seconds()
        scene_hash = self._scene_contract_hash(scene)
        output: list[ShotPlan] = []
        sequence = sequence_start
        for source in semantic_source:
            piece_count = max(1, ceil(source.target_runtime_seconds / limit))
            base, remainder = divmod(source.target_runtime_seconds, piece_count)
            runtimes = tuple(base + (1 if index < remainder else 0) for index in range(piece_count))
            if any(runtime <= 0 or runtime > limit for runtime in runtimes):
                raise GovernedShotPlanningError(
                    f"Unable to decompose semantic Shot {source.shot_id} within "
                    f"the active {limit}s governed cinematic limit"
                )

            for piece_index, runtime in enumerate(runtimes, start=1):
                shot_id = self._shot_id(scene.scene_id, sequence)
                previous_id = self._shot_id(scene.scene_id, sequence - 1) if sequence > 1 else None
                next_id = self._shot_id(scene.scene_id, sequence + 1)
                role = self._coverage_role(
                    source,
                    piece_index,
                    piece_count,
                )
                carries_dialogue = self._carries_dialogue(
                    source,
                    role,
                    piece_index,
                    piece_count,
                )
                output.append(
                    ShotPlan(
                        shot_id=shot_id,
                        scene_id=scene.scene_id,
                        sequence_number=sequence,
                        title=self._decomposed_title(
                            source.title,
                            role,
                        ),
                        narrative_purpose=self._decomposed_purpose(
                            source.narrative_purpose,
                            role,
                        ),
                        production_objective=source.production_objective,
                        target_runtime_seconds=runtime,
                        required_action=self._decomposed_action(
                            source,
                            role,
                            carries_dialogue=carries_dialogue,
                        ),
                        coverage_role=role,
                        dialogue_requirement=(
                            source.dialogue_requirement if carries_dialogue else ""
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
                                    f"Governed cinematic Shot runtime must not exceed "
                                    f"{limit} seconds."
                                ),
                                (
                                    f"Preserve semantic source Shot {source.shot_id}: "
                                    f"{source.title}."
                                ),
                                f"Cinematic coverage role: {role.value}.",
                            )
                        ),
                        scene_contract_hash=scene_hash,
                        status=ShotPlanStatus.DRAFT,
                    )
                )
                sequence += 1

        total = sum(plan.target_runtime_seconds for plan in output)
        expected = (
            sum(plan.target_runtime_seconds for plan in semantic_source)
            if expected_runtime_seconds is None
            else expected_runtime_seconds
        )
        if total != expected:
            raise GovernedShotPlanningError(
                f"Semantic cinematic decomposition produced {total}s but authority "
                f"requires {expected}s"
            )
        return tuple(output)

    @staticmethod
    def _carries_dialogue(
        source: ShotPlan,
        role: CinematicCoverageRole,
        index: int,
        count: int,
    ) -> bool:
        """Carry governed dialogue exactly once, including two-Shot semantic beats."""
        if not source.dialogue_requirement.strip():
            return False
        if role is CinematicCoverageRole.DIALOGUE_DELIVERY:
            return True
        return count == 2 and index == 2 and role is CinematicCoverageRole.RESOLVE

    @staticmethod
    def _coverage_role(
        source: ShotPlan,
        index: int,
        count: int,
    ) -> CinematicCoverageRole:
        if count <= 1:
            return (
                CinematicCoverageRole.DIALOGUE_DELIVERY
                if source.dialogue_requirement.strip()
                else CinematicCoverageRole.PROGRESSION
            )
        if index == 1:
            return CinematicCoverageRole.ESTABLISHING
        if index == count:
            return CinematicCoverageRole.RESOLVE
        if source.dialogue_requirement.strip() and index == min(2, count - 1):
            return CinematicCoverageRole.DIALOGUE_DELIVERY

        interior = index - 2
        roles: tuple[CinematicCoverageRole, ...]
        if count >= 5:
            roles = (
                CinematicCoverageRole.PRIMARY_SUBJECT,
                CinematicCoverageRole.DETAIL_INSERT,
                CinematicCoverageRole.REACTION,
                CinematicCoverageRole.SECONDARY_SUBJECT,
                CinematicCoverageRole.PROGRESSION,
            )
        elif count == 4:
            roles = (
                CinematicCoverageRole.PRIMARY_SUBJECT,
                CinematicCoverageRole.DETAIL_INSERT,
            )
        elif count == 3:
            roles = (CinematicCoverageRole.DETAIL_INSERT,)
        else:
            roles = (CinematicCoverageRole.PROGRESSION,)
        return roles[interior % len(roles)]

    @staticmethod
    def _coverage_label(role: CinematicCoverageRole) -> str:
        return {
            CinematicCoverageRole.UNSPECIFIED: "Coverage",
            CinematicCoverageRole.ESTABLISHING: "Establish",
            CinematicCoverageRole.PRIMARY_SUBJECT: "Primary Subject",
            CinematicCoverageRole.SECONDARY_SUBJECT: "Secondary Subject",
            CinematicCoverageRole.DETAIL_INSERT: "Detail",
            CinematicCoverageRole.DIALOGUE_DELIVERY: "Dialogue",
            CinematicCoverageRole.REACTION: "Reaction",
            CinematicCoverageRole.PROGRESSION: "Progression",
            CinematicCoverageRole.RESOLVE: "Resolve",
        }[role]

    @classmethod
    def _decomposed_title(
        cls,
        title: str,
        role: CinematicCoverageRole,
    ) -> str:
        return f"{title} — {cls._coverage_label(role)}"

    @staticmethod
    def _decomposed_purpose(
        purpose: str,
        role: CinematicCoverageRole,
    ) -> str:
        templates = {
            CinematicCoverageRole.ESTABLISHING: (
                "Establish the geography, participants and visual state required by this "
                f"semantic beat: {purpose}"
            ),
            CinematicCoverageRole.PRIMARY_SUBJECT: (
                "Concentrate on the principal subject or action carrying this semantic beat: "
                f"{purpose}"
            ),
            CinematicCoverageRole.SECONDARY_SUBJECT: (
                "Cover the secondary participant or complementary action that advances this "
                f"semantic beat: {purpose}"
            ),
            CinematicCoverageRole.DETAIL_INSERT: (
                "Reveal an information-bearing visual detail or insert that materially advances "
                f"this semantic beat: {purpose}"
            ),
            CinematicCoverageRole.DIALOGUE_DELIVERY: (
                "Present the governed dialogue delivery while preserving the narrative purpose "
                f"of this semantic beat: {purpose}"
            ),
            CinematicCoverageRole.REACTION: (
                "Show the immediate character response or consequence created by this semantic "
                f"beat: {purpose}"
            ),
            CinematicCoverageRole.PROGRESSION: (
                "Advance the visible action without repeating the establishing composition: "
                f"{purpose}"
            ),
            CinematicCoverageRole.RESOLVE: (
                "Resolve the semantic beat and create a clean editorial handoff to the next "
                f"Shot: {purpose}"
            ),
            CinematicCoverageRole.UNSPECIFIED: purpose,
        }
        return templates[role]

    @classmethod
    def _decomposed_action(
        cls,
        source: ShotPlan,
        role: CinematicCoverageRole,
        *,
        carries_dialogue: bool,
    ) -> str:
        """Create role-specific action without leaking dialogue into non-dialogue coverage."""
        if source.dialogue_requirement.strip() and not carries_dialogue:
            return cls._non_dialogue_decomposed_action(source, role)

        action = source.required_action
        templates = {
            CinematicCoverageRole.ESTABLISHING: (
                "Establish the full spatial relationship and initial state for: "
                f"{action} Do not spend this Shot on a close reaction or insert."
            ),
            CinematicCoverageRole.PRIMARY_SUBJECT: (
                "Isolate the principal subject performing or driving the beat action: "
                f"{action} Avoid repeating the wide establishing composition."
            ),
            CinematicCoverageRole.SECONDARY_SUBJECT: (
                "Shift attention to the secondary participant or complementary action within: "
                f"{action} Preserve eyelines and scene geography."
            ),
            CinematicCoverageRole.DETAIL_INSERT: (
                "Show a specific information-bearing visual detail, display, object, hand action "
                f"or environmental cue that advances: {action} Do not repeat the master view."
            ),
            CinematicCoverageRole.DIALOGUE_DELIVERY: (
                "Frame the speaker delivering the governed dialogue while the physical action "
                f"continues consistently with: {action} Do not invent additional spoken content."
            ),
            CinematicCoverageRole.REACTION: (
                "Show the immediate reaction or decision caused by the preceding action in: "
                f"{action} Preserve identity, orientation and established screen direction."
            ),
            CinematicCoverageRole.PROGRESSION: (
                "Advance the beat with a visibly new stage of the action in: "
                f"{action} Do not simply restage the previous Shot."
            ),
            CinematicCoverageRole.RESOLVE: (
                "Complete the required beat action and leave the visual state ready for the next "
                f"Shot: {action} Avoid introducing new story information."
            ),
            CinematicCoverageRole.UNSPECIFIED: action,
        }
        return templates[role]

    @staticmethod
    def _non_dialogue_decomposed_action(
        source: ShotPlan,
        role: CinematicCoverageRole,
    ) -> str:
        """Describe only observable non-dialogue coverage when dialogue belongs to another Shot."""
        purpose = source.narrative_purpose
        objective = source.production_objective
        templates = {
            CinematicCoverageRole.ESTABLISHING: (
                "Establish the participants, spatial relationship and non-dialogue visual state "
                f"required by the beat. Preserve the production objective: {objective}"
            ),
            CinematicCoverageRole.PRIMARY_SUBJECT: (
                "Show the principal subject's non-dialogue physical action or attention state "
                f"that advances: {purpose}"
            ),
            CinematicCoverageRole.SECONDARY_SUBJECT: (
                "Show the secondary participant's non-dialogue physical action or attention "
                f"state that advances: {purpose}"
            ),
            CinematicCoverageRole.DETAIL_INSERT: (
                "Show a specific information-bearing visual detail, display, object, hand action "
                f"or environmental cue that advances: {purpose} "
                "Do not depict or imply spoken dialogue in this Shot."
            ),
            CinematicCoverageRole.REACTION: (
                "Show the immediate nonverbal reaction, attention shift or physical consequence "
                f"that advances: {purpose}"
            ),
            CinematicCoverageRole.PROGRESSION: (
                "Advance the observable non-dialogue physical state of the beat without repeating "
                f"the previous composition: {purpose}"
            ),
            CinematicCoverageRole.RESOLVE: (
                "Resolve the beat through observable non-dialogue physical state and reaction, "
                f"leaving a clean handoff to the next Shot: {purpose}"
            ),
            CinematicCoverageRole.DIALOGUE_DELIVERY: (
                "Preserve the governed non-dialogue visual state for the beat without introducing "
                f"spoken content: {purpose}"
            ),
            CinematicCoverageRole.UNSPECIFIED: (
                f"Advance the observable non-dialogue action required by: {purpose}"
            ),
        }
        return templates[role]

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
        raw["coverage_role"] = plan.coverage_role.value
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
            coverage_role=CinematicCoverageRole(
                str(raw.get("coverage_role", CinematicCoverageRole.UNSPECIFIED.value))
            ),
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
