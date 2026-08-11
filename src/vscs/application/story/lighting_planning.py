"""Governed lighting planning for Phase 19.3.6."""

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
from .camera_planning import CameraPlan, GovernedCameraPlanningService
from .shot_planning import GovernedShotPlanningService, ShotPlan


class GovernedLightingPlanningError(RuntimeError):
    """Raised when a governed Lighting Plan cannot be processed safely."""


class LightingPlanStatus(StrEnum):
    """Governance state for one Lighting Plan."""

    DRAFT = "draft"
    READY = "ready"


class LightingIntent(StrEnum):
    """Renderer-neutral lighting intent."""

    NATURALISTIC = "naturalistic"
    PRACTICAL_MOTIVATED = "practical_motivated"
    LOW_KEY = "low_key"
    HIGH_KEY = "high_key"
    SILHOUETTE = "silhouette"


class KeyDirection(StrEnum):
    """Primary source direction relative to the camera/subject relationship."""

    MOTIVATED = "motivated"
    FRONT_SIDE = "front_side"
    SIDE = "side"
    BACK = "back"
    TOP = "top"


class LightQuality(StrEnum):
    """Apparent hardness of the dominant source."""

    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"


class ExposureIntent(StrEnum):
    """Exposure priority without renderer-specific exposure settings."""

    BALANCED = "balanced"
    PROTECT_HIGHLIGHTS = "protect_highlights"
    PRESERVE_SHADOW_DETAIL = "preserve_shadow_detail"
    SILHOUETTE_BIASED = "silhouette_biased"


@dataclass(frozen=True, slots=True)
class LightingPlan:
    """One authoritative renderer-neutral lighting contract for a governed Shot."""

    lighting_plan_id: str
    shot_id: str
    lighting_intent: LightingIntent
    key_direction: KeyDirection
    key_quality: LightQuality
    color_temperature_k: int
    fill_level_percent: int
    exposure_intent: ExposureIntent
    source_strategy: str
    shadow_strategy: str
    subject_readability: str
    separation_strategy: str = ""
    continuity_notes: str = ""
    lighting_constraints: tuple[str, ...] = ()
    lighting_profile_asset_id: str = ""
    shot_contract_hash: str = ""
    asset_context_hash: str = ""
    camera_context_hash: str = ""
    lighting_profile_hash: str = ""
    status: LightingPlanStatus = LightingPlanStatus.DRAFT


class GovernedLightingPlanningService:
    """Plan lighting beneath current governed Shot, Asset and Camera authority."""

    FILE_NAME = "lighting_plans.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        shots: GovernedShotPlanningService,
        assets: GovernedAssetResolutionService,
        camera: GovernedCameraPlanningService,
        resolver: AssetResolutionService,
        browser: AssetBrowserService,
    ) -> None:
        self.projects = projects
        self.shots = shots
        self.assets = assets
        self.camera = camera
        self.resolver = resolver
        self.browser = browser

    @property
    def planning_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "planning" / self.FILE_NAME

    def list_plans(self) -> tuple[LightingPlan, ...]:
        path = self.planning_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            plans = tuple(self._from_dict(item) for item in raw.get("lighting_plans", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise GovernedLightingPlanningError(f"Unable to load Lighting Plans: {exc}") from exc
        return tuple(sorted(plans, key=lambda plan: plan.shot_id))

    def plan(self, shot_id: str) -> LightingPlan | None:
        normalized = shot_id.strip().upper()
        return next((plan for plan in self.list_plans() if plan.shot_id == normalized), None)

    def available_lighting_profiles(self) -> tuple[tuple[str, str], ...]:
        result = self.browser.browse(
            AssetBrowserFilter(categories=frozenset({AssetCategory.LIGHTING}))
        )
        return tuple((item.asset_id, item.name) for item in result.items)

    def suggested_plan(self, shot_id: str) -> LightingPlan:
        """Return deterministic conservative lighting defaults without persisting them."""
        shot, camera = self._require_ready_context(shot_id)
        text = " ".join(
            (
                shot.title,
                shot.narrative_purpose,
                shot.production_objective,
                shot.required_action,
                shot.dialogue_requirement,
                " ".join(shot.shot_constraints),
            )
        ).lower()

        intent = LightingIntent.PRACTICAL_MOTIVATED
        direction = KeyDirection.MOTIVATED
        quality = LightQuality.SOFT
        temperature = 4300
        fill = 40
        exposure = ExposureIntent.BALANCED
        source_strategy = (
            "motivate illumination from sources justified by the governed Shot; avoid decorative glow"
        )
        shadow_strategy = "retain soft directional modelling without crushing useful production detail"
        readability = "keep the primary narrative subject readable without flattening the scene"
        separation = "use restrained tonal separation only where required for subject readability"

        if any(term in text for term in ("orbit", "space", "exterior", "planet", "arrival")):
            intent = LightingIntent.NATURALISTIC
            direction = KeyDirection.SIDE
            quality = LightQuality.HARD
            temperature = 5600
            fill = 18
            exposure = ExposureIntent.PROTECT_HIGHLIGHTS
            source_strategy = (
                "use one physically motivated dominant source with restrained indirect fill; do not invent ambient atmospheric glow"
            )
            shadow_strategy = "preserve credible directional shadows while retaining essential subject information"
        if shot.dialogue_requirement.strip():
            intent = LightingIntent.PRACTICAL_MOTIVATED
            direction = KeyDirection.FRONT_SIDE
            quality = LightQuality.SOFT
            temperature = 4300
            fill = 50
            exposure = ExposureIntent.BALANCED
            readability = "maintain natural facial readability and eye detail without glamour lighting"
            separation = "separate speakers subtly from the background while preserving environmental integration"
        if any(term in text for term in ("danger", "threat", "tension", "dark", "night", "horror")):
            intent = LightingIntent.LOW_KEY
            direction = KeyDirection.SIDE
            quality = LightQuality.MEDIUM
            fill = 20
            exposure = ExposureIntent.PROTECT_HIGHLIGHTS
            shadow_strategy = "allow controlled shadow depth while preserving story-critical detail"
        if any(term in text for term in ("medical", "laboratory", "lab", "inspection", "briefing")):
            intent = LightingIntent.HIGH_KEY
            direction = KeyDirection.TOP
            quality = LightQuality.SOFT
            temperature = 4700
            fill = 65
            exposure = ExposureIntent.PRESERVE_SHADOW_DETAIL
            shadow_strategy = "keep shadows open and functional without eliminating depth cues"
        if any(term in text for term in ("silhouette", "backlit", "backlight")):
            intent = LightingIntent.SILHOUETTE
            direction = KeyDirection.BACK
            quality = LightQuality.HARD
            fill = 8
            exposure = ExposureIntent.SILHOUETTE_BIASED
            readability = "preserve intentional silhouette while keeping required story geometry legible"

        return LightingPlan(
            lighting_plan_id=self._lighting_plan_id(shot.shot_id),
            shot_id=shot.shot_id,
            lighting_intent=intent,
            key_direction=direction,
            key_quality=quality,
            color_temperature_k=temperature,
            fill_level_percent=fill,
            exposure_intent=exposure,
            source_strategy=source_strategy,
            shadow_strategy=shadow_strategy,
            subject_readability=readability,
            separation_strategy=separation,
            continuity_notes=self._continuity_notes(shot),
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_context_hash=self._asset_context_hash(shot.shot_id),
            camera_context_hash=self._camera_context_hash(camera),
        )

    def create_suggested(self, shot_id: str) -> LightingPlan:
        if self.plan(shot_id) is not None:
            raise GovernedLightingPlanningError(f"Lighting Plan already exists for {shot_id}")
        plan = self.suggested_plan(shot_id)
        self._write((*self.list_plans(), plan))
        return plan

    def create(
        self,
        *,
        shot_id: str,
        lighting_intent: LightingIntent,
        key_direction: KeyDirection,
        key_quality: LightQuality,
        color_temperature_k: int,
        fill_level_percent: int,
        exposure_intent: ExposureIntent,
        source_strategy: str,
        shadow_strategy: str,
        subject_readability: str,
        separation_strategy: str = "",
        continuity_notes: str = "",
        lighting_constraints: tuple[str, ...] = (),
        lighting_profile_asset_id: str = "",
    ) -> LightingPlan:
        shot, camera = self._require_ready_context(shot_id)
        profile_id = lighting_profile_asset_id.strip().upper()
        if self.plan(shot.shot_id) is not None:
            raise GovernedLightingPlanningError(f"Lighting Plan already exists for {shot.shot_id}")
        plan = LightingPlan(
            lighting_plan_id=self._lighting_plan_id(shot.shot_id),
            shot_id=shot.shot_id,
            lighting_intent=lighting_intent,
            key_direction=key_direction,
            key_quality=key_quality,
            color_temperature_k=self._temperature(color_temperature_k),
            fill_level_percent=self._fill(fill_level_percent),
            exposure_intent=exposure_intent,
            source_strategy=self._required(source_strategy, "Source strategy"),
            shadow_strategy=self._required(shadow_strategy, "Shadow strategy"),
            subject_readability=self._required(subject_readability, "Subject readability"),
            separation_strategy=separation_strategy.strip(),
            continuity_notes=continuity_notes.strip(),
            lighting_constraints=self._values(lighting_constraints),
            lighting_profile_asset_id=profile_id,
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_context_hash=self._asset_context_hash(shot.shot_id),
            camera_context_hash=self._camera_context_hash(camera),
            lighting_profile_hash=self._profile_hash(profile_id),
        )
        self._write((*self.list_plans(), plan))
        return plan

    def update(
        self,
        shot_id: str,
        *,
        lighting_intent: LightingIntent,
        key_direction: KeyDirection,
        key_quality: LightQuality,
        color_temperature_k: int,
        fill_level_percent: int,
        exposure_intent: ExposureIntent,
        source_strategy: str,
        shadow_strategy: str,
        subject_readability: str,
        separation_strategy: str,
        continuity_notes: str,
        lighting_constraints: tuple[str, ...],
        lighting_profile_asset_id: str,
    ) -> LightingPlan:
        current = self._require_plan(shot_id)
        if current.status is not LightingPlanStatus.DRAFT:
            raise GovernedLightingPlanningError(
                "Ready Lighting Plans must return to Draft before editing"
            )
        shot, camera = self._require_ready_context(current.shot_id)
        profile_id = lighting_profile_asset_id.strip().upper()
        updated = replace(
            current,
            lighting_intent=lighting_intent,
            key_direction=key_direction,
            key_quality=key_quality,
            color_temperature_k=self._temperature(color_temperature_k),
            fill_level_percent=self._fill(fill_level_percent),
            exposure_intent=exposure_intent,
            source_strategy=self._required(source_strategy, "Source strategy"),
            shadow_strategy=self._required(shadow_strategy, "Shadow strategy"),
            subject_readability=self._required(subject_readability, "Subject readability"),
            separation_strategy=separation_strategy.strip(),
            continuity_notes=continuity_notes.strip(),
            lighting_constraints=self._values(lighting_constraints),
            lighting_profile_asset_id=profile_id,
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_context_hash=self._asset_context_hash(shot.shot_id),
            camera_context_hash=self._camera_context_hash(camera),
            lighting_profile_hash=self._profile_hash(profile_id),
        )
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> LightingPlan:
        current = self._require_plan(shot_id)
        if current.status is LightingPlanStatus.READY:
            if self.is_production_ready(current):
                return current
            raise GovernedLightingPlanningError(
                "Ready Lighting Plan is stale and must return to Draft before re-approval"
            )
        shot, camera = self._require_ready_context(current.shot_id)
        if current.shot_contract_hash != self._shot_contract_hash(shot):
            raise GovernedLightingPlanningError(
                "Lighting Plan is stale because the Shot contract changed; edit and save it first"
            )
        if not self.assets.shot_ready(current.shot_id):
            raise GovernedLightingPlanningError(
                "Lighting Plan cannot become Ready until every declared Shot asset requirement is Ready"
            )
        if current.asset_context_hash != self._asset_context_hash(current.shot_id):
            raise GovernedLightingPlanningError(
                "Lighting Plan is stale because the resolved asset context changed; edit and save it first"
            )
        if current.camera_context_hash != self._camera_context_hash(camera):
            raise GovernedLightingPlanningError(
                "Lighting Plan is stale because the Camera Plan changed; edit and save it first"
            )
        self._validate_profile(current.lighting_profile_asset_id)
        updated = replace(
            current,
            lighting_profile_hash=self._profile_hash(current.lighting_profile_asset_id),
            status=LightingPlanStatus.READY,
        )
        self._replace(updated)
        return updated

    def return_to_draft(self, shot_id: str) -> LightingPlan:
        current = self._require_plan(shot_id)
        updated = replace(current, status=LightingPlanStatus.DRAFT)
        self._replace(updated)
        return updated

    def delete(self, shot_id: str) -> bool:
        current = self.plan(shot_id)
        if current is None:
            return False
        if current.status is not LightingPlanStatus.DRAFT:
            raise GovernedLightingPlanningError(
                "Ready Lighting Plans must return to Draft before deletion"
            )
        self._write(tuple(plan for plan in self.list_plans() if plan.shot_id != current.shot_id))
        return True

    def is_shot_context_current(self, plan: LightingPlan) -> bool:
        shot = self.shots.plan(plan.shot_id)
        return shot is not None and plan.shot_contract_hash == self._shot_contract_hash(shot)

    def is_asset_context_current(self, plan: LightingPlan) -> bool:
        return plan.asset_context_hash == self._asset_context_hash(plan.shot_id)

    def is_camera_context_current(self, plan: LightingPlan) -> bool:
        camera = self.camera.plan(plan.shot_id)
        return (
            camera is not None
            and self.camera.is_production_ready(camera)
            and plan.camera_context_hash == self._camera_context_hash(camera)
        )

    def is_lighting_profile_current(self, plan: LightingPlan) -> bool:
        if not plan.lighting_profile_asset_id:
            return True
        try:
            resolution = self._profile_resolution(plan.lighting_profile_asset_id)
        except GovernedLightingPlanningError:
            return False
        return (
            resolution.status is AssetResolutionStatus.RESOLVED
            and resolution.fingerprint is not None
            and plan.lighting_profile_hash == resolution.fingerprint.checksum
        )

    def is_production_ready(self, plan: LightingPlan) -> bool:
        shot = self.shots.plan(plan.shot_id)
        return (
            plan.status is LightingPlanStatus.READY
            and shot is not None
            and self.shots.is_production_ready(shot)
            and self.assets.shot_ready(plan.shot_id)
            and self.is_shot_context_current(plan)
            and self.is_asset_context_current(plan)
            and self.is_camera_context_current(plan)
            and self.is_lighting_profile_current(plan)
        )

    def readiness_summary(self, shot_id: str) -> tuple[str, ...]:
        plan = self.plan(shot_id)
        if plan is None:
            return ("No Lighting Plan exists for this Shot.",)
        findings: list[str] = []
        if not self.is_shot_context_current(plan):
            findings.append("Shot contract changed")
        if not self.assets.shot_ready(shot_id):
            findings.append("Shot asset resolution is incomplete or stale")
        elif not self.is_asset_context_current(plan):
            findings.append("Resolved asset context changed")
        if not self.is_camera_context_current(plan):
            findings.append("Camera Plan changed or is no longer production-ready")
        if not self.is_lighting_profile_current(plan):
            findings.append("Lighting profile changed or is no longer production-ready")
        if not findings:
            findings.append("Lighting Plan dependencies are current")
        return tuple(findings)

    def _require_ready_context(self, shot_id: str) -> tuple[ShotPlan, CameraPlan]:
        shot = self.shots.plan(shot_id)
        if shot is None:
            raise GovernedLightingPlanningError(f"Shot Plan not found: {shot_id}")
        if not self.shots.is_production_ready(shot):
            raise GovernedLightingPlanningError(
                "Lighting Planning requires a current Ready governed Shot"
            )
        camera = self.camera.plan(shot.shot_id)
        if camera is None or not self.camera.is_production_ready(camera):
            raise GovernedLightingPlanningError(
                "Lighting Planning requires a current Ready governed Camera Plan"
            )
        return shot, camera

    def _require_plan(self, shot_id: str) -> LightingPlan:
        plan = self.plan(shot_id)
        if plan is None:
            raise GovernedLightingPlanningError(f"Lighting Plan not found for Shot: {shot_id}")
        return plan

    def _replace(self, updated: LightingPlan) -> None:
        self._write(
            tuple(
                updated if plan.shot_id == updated.shot_id else plan for plan in self.list_plans()
            )
        )

    def _write(self, plans: tuple[LightingPlan, ...]) -> None:
        path = self.planning_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "lighting_plans": [
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
            raise GovernedLightingPlanningError(f"Unable to save Lighting Plans: {exc}") from exc

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
        return self.resolver.resolve(
            AssetResolutionRequest(
                asset_id,
                expected_category=AssetCategory.LIGHTING,
                require_approved_asset=True,
                require_cap=True,
                require_approved_cap=True,
                require_approved_references=False,
            )
        )

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
            raise GovernedLightingPlanningError(
                f"Selected Lighting Profile is not production-ready: {diagnostics}"
            )

    @staticmethod
    def _continuity_notes(shot: ShotPlan) -> str:
        values = [
            value.strip() for value in (shot.continuity_in, shot.continuity_out) if value.strip()
        ]
        if not values:
            return "Preserve motivated source direction and exposure relationships across adjacent Shots."
        return " / ".join(values)

    @staticmethod
    def _lighting_plan_id(shot_id: str) -> str:
        return f"{shot_id.strip().upper()}-LGT"

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise GovernedLightingPlanningError(f"{label} is required")
        return normalized

    @staticmethod
    def _temperature(value: int) -> int:
        if value < 1500 or value > 20000:
            raise GovernedLightingPlanningError(
                "Colour temperature must be between 1500 K and 20000 K"
            )
        return value

    @staticmethod
    def _fill(value: int) -> int:
        if value < 0 or value > 100:
            raise GovernedLightingPlanningError("Fill level must be between 0% and 100%")
        return value

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

    @classmethod
    def _camera_context_hash(cls, plan: CameraPlan) -> str:
        payload = asdict(plan)
        payload["shot_size"] = plan.shot_size.value
        payload["angle"] = plan.angle.value
        payload["movement"] = plan.movement.value
        payload["lens_family"] = plan.lens_family.value
        payload["screen_direction"] = plan.screen_direction.value
        payload["camera_constraints"] = list(plan.camera_constraints)
        payload["status"] = plan.status.value
        return cls._checksum(payload)

    @staticmethod
    def _checksum(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _to_dict(plan: LightingPlan) -> dict[str, Any]:
        raw = asdict(plan)
        raw["lighting_intent"] = plan.lighting_intent.value
        raw["key_direction"] = plan.key_direction.value
        raw["key_quality"] = plan.key_quality.value
        raw["exposure_intent"] = plan.exposure_intent.value
        raw["lighting_constraints"] = list(plan.lighting_constraints)
        raw["status"] = plan.status.value
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> LightingPlan:
        return LightingPlan(
            lighting_plan_id=str(raw["lighting_plan_id"]).strip().upper(),
            shot_id=str(raw["shot_id"]).strip().upper(),
            lighting_intent=LightingIntent(str(raw["lighting_intent"])),
            key_direction=KeyDirection(str(raw["key_direction"])),
            key_quality=LightQuality(str(raw["key_quality"])),
            color_temperature_k=int(raw["color_temperature_k"]),
            fill_level_percent=int(raw["fill_level_percent"]),
            exposure_intent=ExposureIntent(str(raw["exposure_intent"])),
            source_strategy=str(raw["source_strategy"]),
            shadow_strategy=str(raw["shadow_strategy"]),
            subject_readability=str(raw["subject_readability"]),
            separation_strategy=str(raw.get("separation_strategy", "")),
            continuity_notes=str(raw.get("continuity_notes", "")),
            lighting_constraints=tuple(str(value) for value in raw.get("lighting_constraints", [])),
            lighting_profile_asset_id=str(raw.get("lighting_profile_asset_id", "")).strip().upper(),
            shot_contract_hash=str(raw.get("shot_contract_hash", "")),
            asset_context_hash=str(raw.get("asset_context_hash", "")),
            camera_context_hash=str(raw.get("camera_context_hash", "")),
            lighting_profile_hash=str(raw.get("lighting_profile_hash", "")),
            status=LightingPlanStatus(str(raw.get("status", LightingPlanStatus.DRAFT.value))),
        )
