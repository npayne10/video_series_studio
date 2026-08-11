"""Governed environment planning for Phase 19.3.7."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService

from .asset_resolver import GovernedAssetResolutionService
from .camera_planning import CameraPlan, GovernedCameraPlanningService
from .lighting_planning import GovernedLightingPlanningService, LightingPlan
from .scene_planning import ScenePlan, ScenePlanningService
from .shot_planning import GovernedShotPlanningService, ShotPlan


class GovernedEnvironmentPlanningError(RuntimeError):
    """Raised when a governed Environment Plan cannot be processed safely."""


class EnvironmentPlanStatus(StrEnum):
    """Governance state for one Environment Plan."""

    DRAFT = "draft"
    READY = "ready"


class EnvironmentContext(StrEnum):
    """Physical context in which the governed Shot occurs."""

    INTERIOR = "interior"
    EXTERIOR_SURFACE = "exterior_surface"
    ATMOSPHERIC = "atmospheric"
    ORBITAL_SPACE = "orbital_space"
    DEEP_SPACE = "deep_space"
    SUBTERRANEAN = "subterranean"
    UNDERWATER = "underwater"


class TimeContext(StrEnum):
    """Environment time/light-cycle context, not a Lighting Plan instruction."""

    NOT_APPLICABLE = "not_applicable"
    DAWN = "dawn"
    DAY = "day"
    DUSK = "dusk"
    NIGHT = "night"
    ARTIFICIAL_CYCLE = "artificial_cycle"


class AtmosphereState(StrEnum):
    """Physical atmospheric state required by production."""

    UNKNOWN = "unknown"
    CONTROLLED = "controlled"
    BREATHABLE = "breathable"
    THIN = "thin"
    DENSE = "dense"
    TOXIC = "toxic"
    VACUUM = "vacuum"
    SUBMERGED = "submerged"


class WeatherState(StrEnum):
    """World/weather condition without renderer implementation details."""

    NONE = "none"
    CLEAR = "clear"
    CLOUD = "cloud"
    RAIN = "rain"
    SNOW = "snow"
    STORM = "storm"
    DUST = "dust"
    FOG = "fog"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class EnvironmentPlan:
    """One authoritative renderer-neutral environment contract for a governed Shot."""

    environment_plan_id: str
    shot_id: str
    environment_context: EnvironmentContext
    time_context: TimeContext
    atmosphere_state: AtmosphereState
    weather_state: WeatherState
    gravity_m_s2: float | None
    pressure_kpa: float | None
    temperature_c: float | None
    visibility_m: float | None
    surface_state: str
    environmental_motion: str
    hazard_notes: str = ""
    continuity_notes: str = ""
    environment_constraints: tuple[str, ...] = ()
    shot_contract_hash: str = ""
    asset_context_hash: str = ""
    camera_context_hash: str = ""
    lighting_context_hash: str = ""
    status: EnvironmentPlanStatus = EnvironmentPlanStatus.DRAFT


class GovernedEnvironmentPlanningService:
    """Plan physical environment state beneath current governed production authority."""

    FILE_NAME = "environment_plans.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        scenes: ScenePlanningService,
        shots: GovernedShotPlanningService,
        assets: GovernedAssetResolutionService,
        camera: GovernedCameraPlanningService,
        lighting: GovernedLightingPlanningService,
    ) -> None:
        self.projects = projects
        self.scenes = scenes
        self.shots = shots
        self.assets = assets
        self.camera = camera
        self.lighting = lighting

    @property
    def planning_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "planning" / self.FILE_NAME

    def list_plans(self) -> tuple[EnvironmentPlan, ...]:
        path = self.planning_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            plans = tuple(self._from_dict(item) for item in raw.get("environment_plans", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise GovernedEnvironmentPlanningError(
                f"Unable to load Environment Plans: {exc}"
            ) from exc
        return tuple(sorted(plans, key=lambda plan: plan.shot_id))

    def plan(self, shot_id: str) -> EnvironmentPlan | None:
        normalized = shot_id.strip().upper()
        return next((plan for plan in self.list_plans() if plan.shot_id == normalized), None)

    def suggested_plan(self, shot_id: str) -> EnvironmentPlan:
        """Return deterministic conservative environment defaults without persisting them."""
        shot, scene, camera, lighting = self._require_ready_context(shot_id)
        setting_text = scene.setting_requirement.lower()
        text = " ".join(
            (
                scene.setting_requirement,
                shot.title,
                shot.narrative_purpose,
                shot.production_objective,
                shot.required_action,
                " ".join(shot.shot_constraints),
            )
        ).lower()

        context = EnvironmentContext.INTERIOR
        time_context = TimeContext.ARTIFICIAL_CYCLE
        atmosphere = AtmosphereState.CONTROLLED
        weather = WeatherState.NONE
        gravity: float | None = None
        pressure: float | None = None
        temperature: float | None = None
        visibility: float | None = None
        surface_state = "stable engineered interior surfaces appropriate to the governed setting"
        motion = "no environmental motion beyond explicitly established story requirements"
        hazards = ""
        constraints = [
            "Do not invent environmental physics, weather or atmospheric properties not established by canon."
        ]

        if any(
            term in setting_text for term in ("orbit", "orbital", "vacuum", "space exterior")
        ):
            context = EnvironmentContext.ORBITAL_SPACE
            time_context = TimeContext.NOT_APPLICABLE
            atmosphere = AtmosphereState.VACUUM
            weather = WeatherState.NONE
            pressure = 0.0
            surface_state = "vacuum environment; no atmospheric surface condition applies"
            motion = (
                "motion is governed by spacecraft/orbital dynamics; no atmospheric wind or drag"
            )
            constraints.append(
                "Do not add atmospheric haze, clouds, wind or aerodynamic effects in vacuum."
            )
        elif any(
            term in setting_text for term in ("deep space", "interstellar", "interplanetary")
        ):
            context = EnvironmentContext.DEEP_SPACE
            time_context = TimeContext.NOT_APPLICABLE
            atmosphere = AtmosphereState.VACUUM
            weather = WeatherState.NONE
            pressure = 0.0
            surface_state = "vacuum environment; no planetary surface condition applies"
            motion = (
                "no environmental motion except physically justified particulate or vehicle motion"
            )
            constraints.append(
                "Preserve vacuum conditions and physically plausible relative motion."
            )
        elif any(
            term in setting_text
            for term in ("descent", "atmosphere", "atmospheric", "cloud layer")
        ):
            context = EnvironmentContext.ATMOSPHERIC
            time_context = self._time_context(text)
            atmosphere = AtmosphereState.UNKNOWN
            weather = self._weather_state(text)
            surface_state = "not applicable during atmospheric flight"
            motion = "airflow, cloud or particulate motion must follow vehicle speed and local atmospheric conditions"
            constraints.append(
                "Atmospheric density/composition remain unspecified unless the governed story establishes them."
            )
        elif any(
            term in setting_text for term in ("underwater", "submerged", "ocean depth", "sea floor")
        ):
            context = EnvironmentContext.UNDERWATER
            time_context = TimeContext.NOT_APPLICABLE
            atmosphere = AtmosphereState.SUBMERGED
            weather = WeatherState.NONE
            visibility = 20.0
            surface_state = (
                "submerged surfaces must reflect local depth, material and sediment conditions"
            )
            motion = (
                "water, suspended particulate and buoyant motion must remain physically coherent"
            )
        elif any(
            term in setting_text
            for term in ("cave", "cavern", "underground", "subterranean", "ruins below")
        ):
            context = EnvironmentContext.SUBTERRANEAN
            time_context = TimeContext.NOT_APPLICABLE
            atmosphere = AtmosphereState.UNKNOWN
            weather = WeatherState.NONE
            surface_state = "subterranean floor/wall condition follows the governed location and established geology"
            motion = (
                "no weather motion; dust or particulate movement only when physically motivated"
            )
        elif any(
            term in setting_text
            for term in (
                "exterior",
                "surface",
                "forest",
                "mountain",
                "lake",
                "river",
                "city",
                "starport",
                "spaceport",
                "planet",
            )
        ):
            context = EnvironmentContext.EXTERIOR_SURFACE
            time_context = self._time_context(text)
            atmosphere = AtmosphereState.UNKNOWN
            weather = self._weather_state(text)
            surface_state = "surface material, terrain and condition must follow the governed location and canonical assets"
            motion = "wind, water, cloud and particulate motion only where supported by the governed setting"

        if "earth" in text:
            gravity = 9.81
            pressure = 101.325 if atmosphere is not AtmosphereState.VACUUM else 0.0
            temperature = 20.0
            if atmosphere is AtmosphereState.UNKNOWN:
                atmosphere = AtmosphereState.BREATHABLE
            if context is EnvironmentContext.EXTERIOR_SURFACE and weather is WeatherState.NONE:
                weather = WeatherState.CLEAR

        if any(term in text for term in ("toxic", "poisonous atmosphere", "unbreathable")):
            atmosphere = AtmosphereState.TOXIC
            hazards = "atmosphere is hazardous to unprotected personnel"
        elif "breathable" in text:
            atmosphere = AtmosphereState.BREATHABLE

        return EnvironmentPlan(
            environment_plan_id=self._environment_plan_id(shot.shot_id),
            shot_id=shot.shot_id,
            environment_context=context,
            time_context=time_context,
            atmosphere_state=atmosphere,
            weather_state=weather,
            gravity_m_s2=gravity,
            pressure_kpa=pressure,
            temperature_c=temperature,
            visibility_m=visibility,
            surface_state=surface_state,
            environmental_motion=motion,
            hazard_notes=hazards,
            continuity_notes=self._continuity_notes(scene, shot),
            environment_constraints=self._values(tuple(constraints)),
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_context_hash=self._asset_context_hash(shot.shot_id),
            camera_context_hash=self._camera_context_hash(camera),
            lighting_context_hash=self._lighting_context_hash(lighting),
        )

    def create_suggested(self, shot_id: str) -> EnvironmentPlan:
        if self.plan(shot_id) is not None:
            raise GovernedEnvironmentPlanningError(f"Environment Plan already exists for {shot_id}")
        plan = self.suggested_plan(shot_id)
        self._write((*self.list_plans(), plan))
        return plan

    def create(
        self,
        *,
        shot_id: str,
        environment_context: EnvironmentContext,
        time_context: TimeContext,
        atmosphere_state: AtmosphereState,
        weather_state: WeatherState,
        gravity_m_s2: float | None,
        pressure_kpa: float | None,
        temperature_c: float | None,
        visibility_m: float | None,
        surface_state: str,
        environmental_motion: str,
        hazard_notes: str = "",
        continuity_notes: str = "",
        environment_constraints: tuple[str, ...] = (),
    ) -> EnvironmentPlan:
        shot, _scene, camera, lighting = self._require_ready_context(shot_id)
        if self.plan(shot.shot_id) is not None:
            raise GovernedEnvironmentPlanningError(
                f"Environment Plan already exists for {shot.shot_id}"
            )
        plan = EnvironmentPlan(
            environment_plan_id=self._environment_plan_id(shot.shot_id),
            shot_id=shot.shot_id,
            environment_context=environment_context,
            time_context=time_context,
            atmosphere_state=atmosphere_state,
            weather_state=weather_state,
            gravity_m_s2=self._optional_range(gravity_m_s2, 0.0, 100.0, "Gravity"),
            pressure_kpa=self._optional_range(pressure_kpa, 0.0, 10000.0, "Pressure"),
            temperature_c=self._optional_range(temperature_c, -273.15, 5000.0, "Temperature"),
            visibility_m=self._optional_range(visibility_m, 0.0, 1_000_000_000.0, "Visibility"),
            surface_state=self._required(surface_state, "Surface/environment state"),
            environmental_motion=self._required(environmental_motion, "Environmental motion"),
            hazard_notes=hazard_notes.strip(),
            continuity_notes=continuity_notes.strip(),
            environment_constraints=self._values(environment_constraints),
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_context_hash=self._asset_context_hash(shot.shot_id),
            camera_context_hash=self._camera_context_hash(camera),
            lighting_context_hash=self._lighting_context_hash(lighting),
        )
        self._validate_physical_consistency(plan)
        self._write((*self.list_plans(), plan))
        return plan

    def update(
        self,
        shot_id: str,
        *,
        environment_context: EnvironmentContext,
        time_context: TimeContext,
        atmosphere_state: AtmosphereState,
        weather_state: WeatherState,
        gravity_m_s2: float | None,
        pressure_kpa: float | None,
        temperature_c: float | None,
        visibility_m: float | None,
        surface_state: str,
        environmental_motion: str,
        hazard_notes: str,
        continuity_notes: str,
        environment_constraints: tuple[str, ...],
    ) -> EnvironmentPlan:
        current = self._require_plan(shot_id)
        if current.status is not EnvironmentPlanStatus.DRAFT:
            raise GovernedEnvironmentPlanningError(
                "Ready Environment Plans must return to Draft before editing"
            )
        shot, _scene, camera, lighting = self._require_ready_context(current.shot_id)
        updated = replace(
            current,
            environment_context=environment_context,
            time_context=time_context,
            atmosphere_state=atmosphere_state,
            weather_state=weather_state,
            gravity_m_s2=self._optional_range(gravity_m_s2, 0.0, 100.0, "Gravity"),
            pressure_kpa=self._optional_range(pressure_kpa, 0.0, 10000.0, "Pressure"),
            temperature_c=self._optional_range(temperature_c, -273.15, 5000.0, "Temperature"),
            visibility_m=self._optional_range(visibility_m, 0.0, 1_000_000_000.0, "Visibility"),
            surface_state=self._required(surface_state, "Surface/environment state"),
            environmental_motion=self._required(environmental_motion, "Environmental motion"),
            hazard_notes=hazard_notes.strip(),
            continuity_notes=continuity_notes.strip(),
            environment_constraints=self._values(environment_constraints),
            shot_contract_hash=self._shot_contract_hash(shot),
            asset_context_hash=self._asset_context_hash(shot.shot_id),
            camera_context_hash=self._camera_context_hash(camera),
            lighting_context_hash=self._lighting_context_hash(lighting),
        )
        self._validate_physical_consistency(updated)
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> EnvironmentPlan:
        current = self._require_plan(shot_id)
        if current.status is EnvironmentPlanStatus.READY:
            if self.is_production_ready(current):
                return current
            raise GovernedEnvironmentPlanningError(
                "Ready Environment Plan is stale and must return to Draft before re-approval"
            )
        shot, _scene, camera, lighting = self._require_ready_context(current.shot_id)
        if current.shot_contract_hash != self._shot_contract_hash(shot):
            raise GovernedEnvironmentPlanningError(
                "Environment Plan is stale because the Shot contract changed; edit and save it first"
            )
        if not self.assets.shot_ready(current.shot_id):
            raise GovernedEnvironmentPlanningError(
                "Environment Plan cannot become Ready until every declared Shot asset requirement is Ready"
            )
        if current.asset_context_hash != self._asset_context_hash(current.shot_id):
            raise GovernedEnvironmentPlanningError(
                "Environment Plan is stale because the resolved asset context changed; edit and save it first"
            )
        if current.camera_context_hash != self._camera_context_hash(camera):
            raise GovernedEnvironmentPlanningError(
                "Environment Plan is stale because the Camera Plan changed; edit and save it first"
            )
        if current.lighting_context_hash != self._lighting_context_hash(lighting):
            raise GovernedEnvironmentPlanningError(
                "Environment Plan is stale because the Lighting Plan changed; edit and save it first"
            )
        self._validate_physical_consistency(current)
        updated = replace(current, status=EnvironmentPlanStatus.READY)
        self._replace(updated)
        return updated

    def return_to_draft(self, shot_id: str) -> EnvironmentPlan:
        current = self._require_plan(shot_id)
        updated = replace(current, status=EnvironmentPlanStatus.DRAFT)
        self._replace(updated)
        return updated

    def delete(self, shot_id: str) -> bool:
        current = self.plan(shot_id)
        if current is None:
            return False
        if current.status is not EnvironmentPlanStatus.DRAFT:
            raise GovernedEnvironmentPlanningError(
                "Ready Environment Plans must return to Draft before deletion"
            )
        self._write(tuple(plan for plan in self.list_plans() if plan.shot_id != current.shot_id))
        return True

    def is_shot_context_current(self, plan: EnvironmentPlan) -> bool:
        shot = self.shots.plan(plan.shot_id)
        return shot is not None and plan.shot_contract_hash == self._shot_contract_hash(shot)

    def is_asset_context_current(self, plan: EnvironmentPlan) -> bool:
        return plan.asset_context_hash == self._asset_context_hash(plan.shot_id)

    def is_camera_context_current(self, plan: EnvironmentPlan) -> bool:
        camera = self.camera.plan(plan.shot_id)
        return (
            camera is not None
            and self.camera.is_production_ready(camera)
            and plan.camera_context_hash == self._camera_context_hash(camera)
        )

    def is_lighting_context_current(self, plan: EnvironmentPlan) -> bool:
        lighting = self.lighting.plan(plan.shot_id)
        return (
            lighting is not None
            and self.lighting.is_production_ready(lighting)
            and plan.lighting_context_hash == self._lighting_context_hash(lighting)
        )

    def is_production_ready(self, plan: EnvironmentPlan) -> bool:
        shot = self.shots.plan(plan.shot_id)
        return (
            plan.status is EnvironmentPlanStatus.READY
            and shot is not None
            and self.shots.is_production_ready(shot)
            and self.assets.shot_ready(plan.shot_id)
            and self.is_shot_context_current(plan)
            and self.is_asset_context_current(plan)
            and self.is_camera_context_current(plan)
            and self.is_lighting_context_current(plan)
        )

    def readiness_summary(self, shot_id: str) -> tuple[str, ...]:
        plan = self.plan(shot_id)
        if plan is None:
            return ("No Environment Plan exists for this Shot.",)
        findings: list[str] = []
        if not self.is_shot_context_current(plan):
            findings.append("Shot contract changed")
        if not self.assets.shot_ready(shot_id):
            findings.append("Shot asset resolution is incomplete or stale")
        elif not self.is_asset_context_current(plan):
            findings.append("Resolved asset context changed")
        if not self.is_camera_context_current(plan):
            findings.append("Camera Plan changed or is no longer production-ready")
        if not self.is_lighting_context_current(plan):
            findings.append("Lighting Plan changed or is no longer production-ready")
        if not findings:
            findings.append("Environment Plan dependencies are current")
        return tuple(findings)

    def setting_requirement(self, shot_id: str) -> str:
        shot = self.shots.plan(shot_id)
        if shot is None:
            return ""
        scene = self.scenes.plan(shot.scene_id)
        return scene.setting_requirement if scene is not None else ""

    def _require_ready_context(
        self, shot_id: str
    ) -> tuple[ShotPlan, ScenePlan, CameraPlan, LightingPlan]:
        shot = self.shots.plan(shot_id)
        if shot is None:
            raise GovernedEnvironmentPlanningError(f"Shot Plan not found: {shot_id}")
        if not self.shots.is_production_ready(shot):
            raise GovernedEnvironmentPlanningError(
                "Environment Planning requires a current Ready governed Shot"
            )
        scene = self.scenes.plan(shot.scene_id)
        if scene is None:
            raise GovernedEnvironmentPlanningError(
                f"Scene Plan not found for governed Shot: {shot.scene_id}"
            )
        camera = self.camera.plan(shot.shot_id)
        if camera is None or not self.camera.is_production_ready(camera):
            raise GovernedEnvironmentPlanningError(
                "Environment Planning requires a current Ready governed Camera Plan"
            )
        lighting = self.lighting.plan(shot.shot_id)
        if lighting is None or not self.lighting.is_production_ready(lighting):
            raise GovernedEnvironmentPlanningError(
                "Environment Planning requires a current Ready governed Lighting Plan"
            )
        return shot, scene, camera, lighting

    def _require_plan(self, shot_id: str) -> EnvironmentPlan:
        plan = self.plan(shot_id)
        if plan is None:
            raise GovernedEnvironmentPlanningError(
                f"Environment Plan not found for Shot: {shot_id}"
            )
        return plan

    def _replace(self, updated: EnvironmentPlan) -> None:
        self._write(
            tuple(
                updated if plan.shot_id == updated.shot_id else plan for plan in self.list_plans()
            )
        )

    def _write(self, plans: tuple[EnvironmentPlan, ...]) -> None:
        path = self.planning_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "environment_plans": [
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
            raise GovernedEnvironmentPlanningError(
                f"Unable to save Environment Plans: {exc}"
            ) from exc

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

    @staticmethod
    def _time_context(text: str) -> TimeContext:
        if any(term in text for term in ("dawn", "sunrise", "early morning")):
            return TimeContext.DAWN
        if any(term in text for term in ("dusk", "sunset", "twilight")):
            return TimeContext.DUSK
        if any(term in text for term in ("night", "midnight")):
            return TimeContext.NIGHT
        return TimeContext.DAY

    @staticmethod
    def _weather_state(text: str) -> WeatherState:
        if any(term in text for term in ("storm", "thunder", "lightning")):
            return WeatherState.STORM
        if "rain" in text:
            return WeatherState.RAIN
        if "snow" in text:
            return WeatherState.SNOW
        if any(term in text for term in ("dust", "sandstorm")):
            return WeatherState.DUST
        if any(term in text for term in ("fog", "mist")):
            return WeatherState.FOG
        if any(term in text for term in ("cloud", "overcast")):
            return WeatherState.CLOUD
        if any(term in text for term in ("clear", "sunny")):
            return WeatherState.CLEAR
        return WeatherState.NONE

    @staticmethod
    def _continuity_notes(scene: ScenePlan, shot: ShotPlan) -> str:
        values = [
            value.strip()
            for value in (
                scene.continuity_in,
                shot.continuity_in,
                shot.continuity_out,
                scene.continuity_out,
            )
            if value.strip()
        ]
        if not values:
            return "Preserve physical environment state across adjacent Shots unless the story explicitly changes it."
        return " / ".join(dict.fromkeys(values))

    @staticmethod
    def _environment_plan_id(shot_id: str) -> str:
        return f"{shot_id.strip().upper()}-ENV"

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise GovernedEnvironmentPlanningError(f"{label} is required")
        return normalized

    @staticmethod
    def _optional_range(
        value: float | None, minimum: float, maximum: float, label: str
    ) -> float | None:
        if value is None:
            return None
        normalized = float(value)
        if normalized < minimum or normalized > maximum:
            raise GovernedEnvironmentPlanningError(
                f"{label} must be between {minimum:g} and {maximum:g} when specified"
            )
        return round(normalized, 4)

    @staticmethod
    def _values(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))

    @staticmethod
    def _validate_physical_consistency(plan: EnvironmentPlan) -> None:
        if plan.atmosphere_state is AtmosphereState.VACUUM:
            if plan.pressure_kpa not in {None, 0.0}:
                raise GovernedEnvironmentPlanningError(
                    "Vacuum environment cannot have non-zero atmospheric pressure"
                )
            if plan.weather_state is not WeatherState.NONE:
                raise GovernedEnvironmentPlanningError(
                    "Vacuum environment cannot have atmospheric weather"
                )
        if (
            plan.environment_context
            in {
                EnvironmentContext.ORBITAL_SPACE,
                EnvironmentContext.DEEP_SPACE,
            }
            and plan.atmosphere_state is not AtmosphereState.VACUUM
        ):
            raise GovernedEnvironmentPlanningError(
                "Space environment context requires vacuum atmosphere state"
            )
        if plan.environment_context is EnvironmentContext.UNDERWATER:
            if plan.atmosphere_state is not AtmosphereState.SUBMERGED:
                raise GovernedEnvironmentPlanningError(
                    "Underwater environment context requires submerged atmosphere state"
                )
            if plan.weather_state is not WeatherState.NONE:
                raise GovernedEnvironmentPlanningError(
                    "Underwater environment does not use atmospheric weather state"
                )

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

    @classmethod
    def _lighting_context_hash(cls, plan: LightingPlan) -> str:
        payload = asdict(plan)
        payload["lighting_intent"] = plan.lighting_intent.value
        payload["key_direction"] = plan.key_direction.value
        payload["key_quality"] = plan.key_quality.value
        payload["exposure_intent"] = plan.exposure_intent.value
        payload["lighting_constraints"] = list(plan.lighting_constraints)
        payload["status"] = plan.status.value
        return cls._checksum(payload)

    @staticmethod
    def _checksum(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _to_dict(plan: EnvironmentPlan) -> dict[str, Any]:
        raw = asdict(plan)
        raw["environment_context"] = plan.environment_context.value
        raw["time_context"] = plan.time_context.value
        raw["atmosphere_state"] = plan.atmosphere_state.value
        raw["weather_state"] = plan.weather_state.value
        raw["environment_constraints"] = list(plan.environment_constraints)
        raw["status"] = plan.status.value
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> EnvironmentPlan:
        return EnvironmentPlan(
            environment_plan_id=str(raw["environment_plan_id"]).strip().upper(),
            shot_id=str(raw["shot_id"]).strip().upper(),
            environment_context=EnvironmentContext(str(raw["environment_context"])),
            time_context=TimeContext(str(raw["time_context"])),
            atmosphere_state=AtmosphereState(str(raw["atmosphere_state"])),
            weather_state=WeatherState(str(raw["weather_state"])),
            gravity_m_s2=GovernedEnvironmentPlanningService._optional_float(
                raw.get("gravity_m_s2")
            ),
            pressure_kpa=GovernedEnvironmentPlanningService._optional_float(
                raw.get("pressure_kpa")
            ),
            temperature_c=GovernedEnvironmentPlanningService._optional_float(
                raw.get("temperature_c")
            ),
            visibility_m=GovernedEnvironmentPlanningService._optional_float(
                raw.get("visibility_m")
            ),
            surface_state=str(raw["surface_state"]),
            environmental_motion=str(raw["environmental_motion"]),
            hazard_notes=str(raw.get("hazard_notes", "")),
            continuity_notes=str(raw.get("continuity_notes", "")),
            environment_constraints=tuple(
                str(value) for value in raw.get("environment_constraints", [])
            ),
            shot_contract_hash=str(raw.get("shot_contract_hash", "")),
            asset_context_hash=str(raw.get("asset_context_hash", "")),
            camera_context_hash=str(raw.get("camera_context_hash", "")),
            lighting_context_hash=str(raw.get("lighting_context_hash", "")),
            status=EnvironmentPlanStatus(str(raw.get("status", EnvironmentPlanStatus.DRAFT.value))),
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return None if value is None else float(value)
