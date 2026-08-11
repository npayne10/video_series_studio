"""Governed camera planning for Phase 19.3.5."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.asset_resolution import (
    AssetBrowserFilter,
    AssetBrowserService,
    AssetResolutionRequest,
    AssetResolutionResult,
    AssetResolutionService,
    AssetResolutionStatus,
)
from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.domain.assets import AssetCategory

from .asset_resolver import GovernedAssetResolutionService
from .shot_planning import GovernedShotPlanningService, ShotPlan


class GovernedCameraPlanningError(RuntimeError):
    """Raised when a governed Camera Plan cannot be processed safely."""


class CameraPlanStatus(StrEnum):
    """Governance state for one Camera Plan."""

    DRAFT = "draft"
    READY = "ready"


class ShotSize(StrEnum):
    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"
    INSERT = "insert"


class CameraAngle(StrEnum):
    EYE_LEVEL = "eye_level"
    HIGH = "high"
    LOW = "low"
    OVER_SHOULDER = "over_shoulder"
    TOP_DOWN = "top_down"


class CameraMovement(StrEnum):
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    TRACK = "track"
    PUSH_IN = "push_in"
    PULL_BACK = "pull_back"
    CRANE = "crane"
    ORBIT = "orbit"


class LensFamily(StrEnum):
    ULTRA_WIDE = "ultra_wide"
    WIDE = "wide"
    NORMAL = "normal"
    PORTRAIT = "portrait"
    TELEPHOTO = "telephoto"
    MACRO = "macro"


class ScreenDirection(StrEnum):
    PRESERVE_PREVIOUS = "preserve_previous"
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class CameraPlan:
    """One authoritative renderer-neutral camera contract for a governed Shot."""

    camera_plan_id: str
    shot_id: str
    shot_size: ShotSize
    angle: CameraAngle
    movement: CameraMovement
    lens_family: LensFamily
    focal_length_mm: int
    camera_height_m: float
    screen_direction: ScreenDirection
    composition: str
    focus_strategy: str
    movement_notes: str = ""
    continuity_notes: str = ""
    camera_constraints: tuple[str, ...] = ()
    camera_profile_asset_id: str = ""
    shot_contract_hash: str = ""
    asset_context_hash: str = ""
    camera_profile_hash: str = ""
    status: CameraPlanStatus = CameraPlanStatus.DRAFT


class GovernedCameraPlanningService:
    """Plan camera intent beneath current governed Shots and resolved asset context."""

    FILE_NAME = "camera_plans.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        shots: GovernedShotPlanningService,
        assets: GovernedAssetResolutionService,
        resolver: AssetResolutionService,
        browser: AssetBrowserService,
    ) -> None:
        self.projects = projects
        self.shots = shots
        self.assets = assets
        self.resolver = resolver
        self.browser = browser

    @property
    def planning_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "planning" / self.FILE_NAME

    def list_plans(self) -> tuple[CameraPlan, ...]:
        path = self.planning_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            plans = tuple(self._from_dict(item) for item in raw.get("camera_plans", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise GovernedCameraPlanningError(f"Unable to load Camera Plans: {exc}") from exc
        return tuple(sorted(plans, key=lambda plan: plan.shot_id))

    def plan(self, shot_id: str) -> CameraPlan | None:
        normalized = shot_id.strip().upper()
        return next((plan for plan in self.list_plans() if plan.shot_id == normalized), None)

    def available_camera_profiles(self) -> tuple[tuple[str, str], ...]:
        result = self.browser.browse(
            AssetBrowserFilter(categories=frozenset({AssetCategory.CAMERA}))
        )
        return tuple((item.asset_id, item.name) for item in result.items)

    def suggested_plan(self, shot_id: str) -> CameraPlan:
        """Return deterministic production-oriented camera defaults without persisting them."""
        shot = self._require_ready_shot(shot_id)
        text = " ".join(
            (
                shot.title,
                shot.narrative_purpose,
                shot.production_objective,
                shot.required_action,
                shot.dialogue_requirement,
            )
        ).lower()
        shot_size = ShotSize.MEDIUM
        angle = CameraAngle.EYE_LEVEL
        movement = CameraMovement.STATIC
        lens_family = LensFamily.NORMAL
        focal_length = 50
        composition = "centre the primary narrative action with stable headroom and lead room"
        focus_strategy = "hold primary subject focus with physically plausible depth of field"
        movement_notes = "keep movement restrained and mechanically plausible"

        if any(term in text for term in ("establish", "arrival", "orbit", "city", "environment")):
            shot_size = ShotSize.WIDE
            lens_family = LensFamily.WIDE
            focal_length = 28
            composition = "prioritise readable spatial geography, scale and subject placement"
            focus_strategy = "maintain readable, physically plausible depth across the environment and primary subject"
        if shot.dialogue_requirement.strip():
            shot_size = ShotSize.MEDIUM_CLOSE
            lens_family = LensFamily.NORMAL
            focal_length = 50
            composition = "preserve eye-line, conversational screen direction and natural headroom"
        if any(term in text for term in ("reaction", "realises", "recognises")):
            shot_size = ShotSize.CLOSE_UP
            movement = CameraMovement.PUSH_IN
            lens_family = LensFamily.PORTRAIT
            focal_length = 85
            composition = "prioritise the reaction without distorting facial perspective"
            movement_notes = "use a slow physically motivated push-in without abrupt acceleration"
        if any(
            term in text for term in ("run", "walk", "fly", "move", "cross", "approach", "action")
        ):
            movement = CameraMovement.TRACK
            if shot_size in {ShotSize.MEDIUM, ShotSize.MEDIUM_CLOSE}:
                shot_size = ShotSize.WIDE
                lens_family = LensFamily.WIDE
                focal_length = 35
            movement_notes = (
                "track at a stable speed matched to subject motion; avoid impossible acceleration"
            )

        return CameraPlan(
            camera_plan_id=self._camera_plan_id(shot.shot_id),
            shot_id=shot.shot_id,
            shot_size=shot_size,
            angle=angle,
            movement=movement,
            lens_family=lens_family,
            focal_length_mm=focal_length,
            camera_height_m=1.6,
            screen_direction=ScreenDirection.PRESERVE_PREVIOUS,
            composition=composition,
            focus_strategy=focus_strategy,
            movement_notes=movement_notes,
            continuity_notes=self._continuity_notes(shot),
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_context_hash=self._asset_context_hash(shot.shot_id),
        )

    def create_suggested(self, shot_id: str) -> CameraPlan:
        if self.plan(shot_id) is not None:
            raise GovernedCameraPlanningError(f"Camera Plan already exists for {shot_id}")
        plan = self.suggested_plan(shot_id)
        self._write((*self.list_plans(), plan))
        return plan

    def create(
        self,
        *,
        shot_id: str,
        shot_size: ShotSize,
        angle: CameraAngle,
        movement: CameraMovement,
        lens_family: LensFamily,
        focal_length_mm: int,
        camera_height_m: float,
        screen_direction: ScreenDirection,
        composition: str,
        focus_strategy: str,
        movement_notes: str = "",
        continuity_notes: str = "",
        camera_constraints: tuple[str, ...] = (),
        camera_profile_asset_id: str = "",
    ) -> CameraPlan:
        shot = self._require_ready_shot(shot_id)
        if self.plan(shot.shot_id) is not None:
            raise GovernedCameraPlanningError(f"Camera Plan already exists for {shot.shot_id}")
        profile_id = camera_profile_asset_id.strip().upper()
        plan = CameraPlan(
            camera_plan_id=self._camera_plan_id(shot.shot_id),
            shot_id=shot.shot_id,
            shot_size=shot_size,
            angle=angle,
            movement=movement,
            lens_family=lens_family,
            focal_length_mm=self._focal_length(focal_length_mm),
            camera_height_m=self._camera_height(camera_height_m),
            screen_direction=screen_direction,
            composition=self._required(composition, "Composition"),
            focus_strategy=self._required(focus_strategy, "Focus strategy"),
            movement_notes=movement_notes.strip(),
            continuity_notes=continuity_notes.strip(),
            camera_constraints=self._values(camera_constraints),
            camera_profile_asset_id=profile_id,
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_context_hash=self._asset_context_hash(shot.shot_id),
            camera_profile_hash=self._profile_hash(profile_id),
        )
        self._write((*self.list_plans(), plan))
        return plan

    def update(
        self,
        shot_id: str,
        *,
        shot_size: ShotSize,
        angle: CameraAngle,
        movement: CameraMovement,
        lens_family: LensFamily,
        focal_length_mm: int,
        camera_height_m: float,
        screen_direction: ScreenDirection,
        composition: str,
        focus_strategy: str,
        movement_notes: str,
        continuity_notes: str,
        camera_constraints: tuple[str, ...],
        camera_profile_asset_id: str,
    ) -> CameraPlan:
        current = self._require_plan(shot_id)
        if current.status is not CameraPlanStatus.DRAFT:
            raise GovernedCameraPlanningError(
                "Ready Camera Plans must return to Draft before editing"
            )
        shot = self._require_ready_shot(current.shot_id)
        profile_id = camera_profile_asset_id.strip().upper()
        updated = replace(
            current,
            shot_size=shot_size,
            angle=angle,
            movement=movement,
            lens_family=lens_family,
            focal_length_mm=self._focal_length(focal_length_mm),
            camera_height_m=self._camera_height(camera_height_m),
            screen_direction=screen_direction,
            composition=self._required(composition, "Composition"),
            focus_strategy=self._required(focus_strategy, "Focus strategy"),
            movement_notes=movement_notes.strip(),
            continuity_notes=continuity_notes.strip(),
            camera_constraints=self._values(camera_constraints),
            camera_profile_asset_id=profile_id,
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_context_hash=self._asset_context_hash(shot.shot_id),
            camera_profile_hash=self._profile_hash(profile_id),
        )
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> CameraPlan:
        current = self._require_plan(shot_id)
        if current.status is CameraPlanStatus.READY:
            if self.is_production_ready(current):
                return current
            raise GovernedCameraPlanningError(
                "Ready Camera Plan is stale and must return to Draft before re-approval"
            )
        shot = self._require_ready_shot(current.shot_id)
        if current.shot_contract_hash != self._shot_contract_hash(shot):
            raise GovernedCameraPlanningError(
                "Camera Plan is stale because the Shot contract changed; edit and save it first"
            )
        if not self.assets.shot_ready(current.shot_id):
            raise GovernedCameraPlanningError(
                "Camera Plan cannot become Ready until every declared Shot asset requirement is Ready"
            )
        if current.asset_context_hash != self._asset_context_hash(current.shot_id):
            raise GovernedCameraPlanningError(
                "Camera Plan is stale because the resolved asset context changed; edit and save it first"
            )
        self._validate_profile(current.camera_profile_asset_id)
        updated = replace(
            current,
            camera_profile_hash=self._profile_hash(current.camera_profile_asset_id),
            status=CameraPlanStatus.READY,
        )
        self._replace(updated)
        return updated

    def return_to_draft(self, shot_id: str) -> CameraPlan:
        current = self._require_plan(shot_id)
        updated = replace(current, status=CameraPlanStatus.DRAFT)
        self._replace(updated)
        return updated

    def delete(self, shot_id: str) -> bool:
        current = self.plan(shot_id)
        if current is None:
            return False
        if current.status is not CameraPlanStatus.DRAFT:
            raise GovernedCameraPlanningError(
                "Ready Camera Plans must return to Draft before deletion"
            )
        self._write(tuple(plan for plan in self.list_plans() if plan.shot_id != current.shot_id))
        return True

    def is_upstream_current(self, plan: CameraPlan) -> bool:
        shot = self.shots.plan(plan.shot_id)
        return shot is not None and plan.shot_contract_hash == self._shot_contract_hash(shot)

    def is_asset_context_current(self, plan: CameraPlan) -> bool:
        return plan.asset_context_hash == self._asset_context_hash(plan.shot_id)

    def is_camera_profile_current(self, plan: CameraPlan) -> bool:
        if not plan.camera_profile_asset_id:
            return True
        try:
            resolution = self._profile_resolution(plan.camera_profile_asset_id)
        except GovernedCameraPlanningError:
            return False
        return (
            resolution.status is AssetResolutionStatus.RESOLVED
            and resolution.fingerprint is not None
            and plan.camera_profile_hash == resolution.fingerprint.checksum
        )

    def is_production_ready(self, plan: CameraPlan) -> bool:
        shot = self.shots.plan(plan.shot_id)
        return (
            plan.status is CameraPlanStatus.READY
            and shot is not None
            and self.shots.is_production_ready(shot)
            and self.assets.shot_ready(plan.shot_id)
            and self.is_upstream_current(plan)
            and self.is_asset_context_current(plan)
            and self.is_camera_profile_current(plan)
        )

    def readiness_summary(self, shot_id: str) -> tuple[str, ...]:
        plan = self.plan(shot_id)
        if plan is None:
            return ("No Camera Plan exists for this Shot.",)
        findings: list[str] = []
        if not self.is_upstream_current(plan):
            findings.append("Shot contract changed")
        if not self.assets.shot_ready(shot_id):
            findings.append("Shot asset resolution is incomplete or stale")
        elif not self.is_asset_context_current(plan):
            findings.append("Resolved asset context changed")
        if not self.is_camera_profile_current(plan):
            findings.append("Camera profile changed or is no longer production-ready")
        if not findings:
            findings.append("Camera Plan dependencies are current")
        return tuple(findings)

    def _require_ready_shot(self, shot_id: str) -> ShotPlan:
        shot = self.shots.plan(shot_id)
        if shot is None:
            raise GovernedCameraPlanningError(f"Shot Plan not found: {shot_id}")
        if not self.shots.is_production_ready(shot):
            raise GovernedCameraPlanningError(
                "Camera Planning requires a current Ready governed Shot"
            )
        return shot

    def _require_plan(self, shot_id: str) -> CameraPlan:
        plan = self.plan(shot_id)
        if plan is None:
            raise GovernedCameraPlanningError(f"Camera Plan not found for Shot: {shot_id}")
        return plan

    def _replace(self, updated: CameraPlan) -> None:
        self._write(
            tuple(
                updated if plan.shot_id == updated.shot_id else plan for plan in self.list_plans()
            )
        )

    def _write(self, plans: tuple[CameraPlan, ...]) -> None:
        path = self.planning_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "camera_plans": [
                self._to_dict(plan) for plan in sorted(plans, key=lambda item: item.shot_id)
            ],
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
            raise GovernedCameraPlanningError(f"Unable to save Camera Plans: {exc}") from exc

    def _asset_context_hash(self, shot_id: str) -> str:
        bindings = self.assets.list_bindings(shot_id=shot_id)
        payload = [
            {
                "binding_id": binding.binding_id,
                "sequence_number": binding.sequence_number,
                "role": binding.role,
                "expected_category": binding.expected_category.value,
                "asset_id": binding.asset_id,
                "shot_contract_hash": binding.shot_contract_hash,
                "asset_dependency_hash": binding.asset_dependency_hash,
                "status": binding.status.value,
                "production_ready": self.assets.is_production_ready(binding),
            }
            for binding in bindings
        ]
        return self._checksum(payload)

    def _profile_resolution(self, asset_id: str) -> AssetResolutionResult:
        result = self.resolver.resolve(
            AssetResolutionRequest(
                asset_id,
                expected_category=AssetCategory.CAMERA,
                require_approved_asset=True,
                require_cap=True,
                require_approved_cap=True,
                require_approved_references=False,
            )
        )
        return result

    def _profile_hash(self, asset_id: str) -> str:
        if not asset_id:
            return ""
        result = self._profile_resolution(asset_id)
        return result.fingerprint.checksum if result.fingerprint is not None else ""

    def _validate_profile(self, asset_id: str) -> None:
        if not asset_id:
            return
        result = self._profile_resolution(asset_id)
        if result.status is not AssetResolutionStatus.RESOLVED:
            diagnostics = (
                "; ".join(item.message for item in result.diagnostics) or result.status.value
            )
            raise GovernedCameraPlanningError(
                f"Selected Camera Profile is not production-ready: {diagnostics}"
            )

    @staticmethod
    def _continuity_notes(shot: ShotPlan) -> str:
        values = [
            value.strip() for value in (shot.continuity_in, shot.continuity_out) if value.strip()
        ]
        if not values:
            return "Preserve screen direction and visual geography established by the surrounding Shots."
        return " / ".join(values)

    @staticmethod
    def _camera_plan_id(shot_id: str) -> str:
        return f"{shot_id.strip().upper()}-CAM"

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise GovernedCameraPlanningError(f"{label} is required")
        return normalized

    @staticmethod
    def _focal_length(value: int) -> int:
        if value < 8 or value > 1200:
            raise GovernedCameraPlanningError(
                "Focal length must be between 8 mm and 1200 mm (full-frame equivalent)"
            )
        return value

    @staticmethod
    def _camera_height(value: float) -> float:
        if value < 0.05 or value > 100.0:
            raise GovernedCameraPlanningError("Camera height must be between 0.05 m and 100 m")
        return round(float(value), 3)

    @staticmethod
    def _values(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))

    @classmethod
    def _shot_contract_hash(cls, shot: ShotPlan) -> str:
        payload = {
            "shot_id": shot.shot_id,
            "scene_id": shot.scene_id,
            "sequence_number": shot.sequence_number,
            "title": shot.title,
            "narrative_purpose": shot.narrative_purpose,
            "production_objective": shot.production_objective,
            "target_runtime_seconds": shot.target_runtime_seconds,
            "required_action": shot.required_action,
            "dialogue_requirement": shot.dialogue_requirement,
            "continuity_in": shot.continuity_in,
            "continuity_out": shot.continuity_out,
            "shot_constraints": list(shot.shot_constraints),
            "scene_contract_hash": shot.scene_contract_hash,
        }
        return cls._checksum(payload)

    @staticmethod
    def _checksum(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _to_dict(plan: CameraPlan) -> dict[str, Any]:
        raw = asdict(plan)
        raw["shot_size"] = plan.shot_size.value
        raw["angle"] = plan.angle.value
        raw["movement"] = plan.movement.value
        raw["lens_family"] = plan.lens_family.value
        raw["screen_direction"] = plan.screen_direction.value
        raw["camera_constraints"] = list(plan.camera_constraints)
        raw["status"] = plan.status.value
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> CameraPlan:
        return CameraPlan(
            camera_plan_id=str(raw["camera_plan_id"]).strip().upper(),
            shot_id=str(raw["shot_id"]).strip().upper(),
            shot_size=ShotSize(str(raw["shot_size"])),
            angle=CameraAngle(str(raw["angle"])),
            movement=CameraMovement(str(raw["movement"])),
            lens_family=LensFamily(str(raw["lens_family"])),
            focal_length_mm=int(raw["focal_length_mm"]),
            camera_height_m=float(raw["camera_height_m"]),
            screen_direction=ScreenDirection(str(raw["screen_direction"])),
            composition=str(raw["composition"]),
            focus_strategy=str(raw["focus_strategy"]),
            movement_notes=str(raw.get("movement_notes", "")),
            continuity_notes=str(raw.get("continuity_notes", "")),
            camera_constraints=tuple(str(value) for value in raw.get("camera_constraints", [])),
            camera_profile_asset_id=str(raw.get("camera_profile_asset_id", "")).strip().upper(),
            shot_contract_hash=str(raw.get("shot_contract_hash", "")),
            asset_context_hash=str(raw.get("asset_context_hash", "")),
            camera_profile_hash=str(raw.get("camera_profile_hash", "")),
            status=CameraPlanStatus(str(raw.get("status", CameraPlanStatus.DRAFT.value))),
        )
