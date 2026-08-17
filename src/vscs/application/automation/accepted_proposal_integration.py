"""Bridge accepted automation proposals into their existing governed authoring owners.

Accepted automation remains proposal authority only. This module changes the source used
when a governed Draft is explicitly created; it never marks that Draft Ready and never
bypasses the existing planner prerequisites or production-review gates.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from vscs.application.action_performance import (
    ActionPerformanceCompilerService,
    ActionPerformanceDraft,
)
from vscs.application.continuity_compiler import (
    ContinuityCompilationDraft,
    ContinuityCompilerService,
)
from vscs.application.story import (
    AtmosphereState,
    CameraAngle,
    CameraMovement,
    CameraPlan,
    EnvironmentContext,
    EnvironmentPlan,
    ExposureIntent,
    GovernedCameraPlanningError,
    GovernedCameraPlanningService,
    GovernedEnvironmentPlanningError,
    GovernedEnvironmentPlanningService,
    GovernedLightingPlanningError,
    GovernedLightingPlanningService,
    KeyDirection,
    LensFamily,
    LightingIntent,
    LightingPlan,
    LightQuality,
    ScreenDirection,
    ShotSize,
    TimeContext,
    WeatherState,
)

from .contracts import AutomationProposal, AutomationProposalType
from .service import AutomationProposalService

_PROPOSALS: AutomationProposalService | None = None
_INSTALLED = False


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _integer(payload: dict[str, Any], key: str) -> int:
    return int(payload[key])


def _float(payload: dict[str, Any], key: str) -> float:
    return float(payload[key])


def _optional_float(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    return None if value is None or value == "" else float(value)


def _compiled_revision(proposals: AutomationProposalService) -> str:
    directory = proposals.projects.project_directory
    if directory is None:
        return ""
    path = directory / "automation" / "automation_compilation.json"
    if not path.is_file():
        return ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        report = raw.get("report", {})
        if not isinstance(report, dict):
            return ""
        return str(report.get("source_revision", "")).strip()
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return ""


def accepted_current_proposal(
    proposal_type: AutomationProposalType,
    target_id: str,
) -> AutomationProposal | None:
    """Return the accepted proposal for the current compiled Story revision and target."""
    proposals = _PROPOSALS
    if proposals is None:
        return None
    revision = _compiled_revision(proposals)
    if not revision:
        return None
    normalized = target_id.strip().upper()
    matches = tuple(
        proposal
        for proposal in proposals.list_proposals()
        if proposal.proposal_type is proposal_type
        and proposal.target_id == normalized
        and proposal.provenance.source_revision == revision
        and proposal.consumable
    )
    if not matches:
        return None
    return max(
        matches,
        key=lambda proposal: (
            proposal.provenance.proposal_version,
            proposal.provenance.generated_at,
            proposal.proposal_id,
        ),
    )


def _camera_from_proposal(base: CameraPlan, proposal: AutomationProposal) -> CameraPlan:
    payload = proposal.payload
    try:
        return replace(
            base,
            shot_size=ShotSize(str(payload["shot_size"])),
            angle=CameraAngle(str(payload["angle"])),
            movement=CameraMovement(str(payload["movement"])),
            lens_family=LensFamily(str(payload["lens_family"])),
            focal_length_mm=_integer(payload, "focal_length_mm"),
            camera_height_m=_float(payload, "camera_height_m"),
            screen_direction=ScreenDirection(str(payload["screen_direction"])),
            composition=str(payload["composition"]).strip(),
            focus_strategy=str(payload["focus_strategy"]).strip(),
            movement_notes=str(payload.get("movement_notes", "")).strip(),
            continuity_notes=str(payload.get("continuity_notes", "")).strip(),
            camera_constraints=_strings(payload.get("camera_constraints")),
            camera_profile_asset_id=str(payload.get("camera_profile_asset_id", "")).strip().upper(),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GovernedCameraPlanningError(
            f"Accepted Camera proposal {proposal.proposal_id} cannot seed Camera Planning: {exc}"
        ) from exc


def _lighting_from_proposal(base: LightingPlan, proposal: AutomationProposal) -> LightingPlan:
    payload = proposal.payload
    try:
        return replace(
            base,
            lighting_intent=LightingIntent(str(payload["lighting_intent"])),
            key_direction=KeyDirection(str(payload["key_direction"])),
            key_quality=LightQuality(str(payload["key_quality"])),
            color_temperature_k=_integer(payload, "color_temperature_k"),
            fill_level_percent=_integer(payload, "fill_level_percent"),
            exposure_intent=ExposureIntent(str(payload["exposure_intent"])),
            source_strategy=str(payload["source_strategy"]).strip(),
            shadow_strategy=str(payload["shadow_strategy"]).strip(),
            subject_readability=str(payload["subject_readability"]).strip(),
            separation_strategy=str(payload.get("separation_strategy", "")).strip(),
            continuity_notes=str(payload.get("continuity_notes", "")).strip(),
            lighting_constraints=_strings(payload.get("lighting_constraints")),
            lighting_profile_asset_id=str(payload.get("lighting_profile_asset_id", ""))
            .strip()
            .upper(),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GovernedLightingPlanningError(
            f"Accepted Lighting proposal {proposal.proposal_id} cannot seed Lighting Planning: {exc}"
        ) from exc


def _environment_from_proposal(
    base: EnvironmentPlan,
    proposal: AutomationProposal,
) -> EnvironmentPlan:
    payload = proposal.payload
    try:
        return replace(
            base,
            environment_context=EnvironmentContext(str(payload["environment_context"])),
            time_context=TimeContext(str(payload["time_context"])),
            atmosphere_state=AtmosphereState(str(payload["atmosphere_state"])),
            weather_state=WeatherState(str(payload["weather_state"])),
            gravity_m_s2=_optional_float(payload, "gravity_m_s2"),
            pressure_kpa=_optional_float(payload, "pressure_kpa"),
            temperature_c=_optional_float(payload, "temperature_c"),
            visibility_m=_optional_float(payload, "visibility_m"),
            surface_state=str(payload["surface_state"]).strip(),
            environmental_motion=str(payload["environmental_motion"]).strip(),
            hazard_notes=str(payload.get("hazard_notes", "")).strip(),
            continuity_notes=str(payload.get("continuity_notes", "")).strip(),
            environment_constraints=_strings(payload.get("environment_constraints")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GovernedEnvironmentPlanningError(
            f"Accepted Environment proposal {proposal.proposal_id} cannot seed Environment Planning: {exc}"
        ) from exc


def install_accepted_proposal_consumption(proposals: AutomationProposalService) -> None:
    """Install accepted-proposal-first Draft creation over the established services."""
    global _INSTALLED, _PROPOSALS
    _PROPOSALS = proposals
    if _INSTALLED:
        return

    original_action_create: Callable[
        [ActionPerformanceCompilerService, str], ActionPerformanceDraft
    ]
    original_action_create = ActionPerformanceCompilerService.create_from_current_package
    original_camera_suggested: Callable[[GovernedCameraPlanningService, str], CameraPlan]
    original_camera_suggested = GovernedCameraPlanningService.suggested_plan
    original_lighting_suggested: Callable[[GovernedLightingPlanningService, str], LightingPlan]
    original_lighting_suggested = GovernedLightingPlanningService.suggested_plan
    original_environment_suggested: Callable[
        [GovernedEnvironmentPlanningService, str], EnvironmentPlan
    ]
    original_environment_suggested = GovernedEnvironmentPlanningService.suggested_plan
    original_continuity_create: Callable[
        [ContinuityCompilerService, str], ContinuityCompilationDraft
    ]
    original_continuity_create = ContinuityCompilerService.create_from_current_package

    def action_create(
        service: ActionPerformanceCompilerService,
        shot_id: str,
    ) -> ActionPerformanceDraft:
        draft = original_action_create(service, shot_id)
        proposal = accepted_current_proposal(
            AutomationProposalType.ACTION_PERFORMANCE, draft.shot_id
        )
        if proposal is None:
            return draft
        payload = proposal.payload
        return service.save(
            draft.shot_id,
            temporal_narrative=str(payload.get("temporal_narrative", "")).strip(),
            spoken_content=str(payload.get("spoken_content", "")).strip(),
            performance_direction=str(payload.get("performance_direction", "")).strip(),
            opening_state=str(payload.get("opening_state", "")).strip(),
            closing_state=str(payload.get("closing_state", "")).strip(),
            timing_notes=str(payload.get("timing_notes", "")).strip(),
        )

    def camera_suggested(service: GovernedCameraPlanningService, shot_id: str) -> CameraPlan:
        base = original_camera_suggested(service, shot_id)
        proposal = accepted_current_proposal(AutomationProposalType.CAMERA, base.shot_id)
        return _camera_from_proposal(base, proposal) if proposal is not None else base

    def lighting_suggested(service: GovernedLightingPlanningService, shot_id: str) -> LightingPlan:
        base = original_lighting_suggested(service, shot_id)
        proposal = accepted_current_proposal(AutomationProposalType.LIGHTING, base.shot_id)
        return _lighting_from_proposal(base, proposal) if proposal is not None else base

    def environment_suggested(
        service: GovernedEnvironmentPlanningService,
        shot_id: str,
    ) -> EnvironmentPlan:
        base = original_environment_suggested(service, shot_id)
        proposal = accepted_current_proposal(AutomationProposalType.ENVIRONMENT, base.shot_id)
        return _environment_from_proposal(base, proposal) if proposal is not None else base

    def continuity_create(
        service: ContinuityCompilerService,
        shot_id: str,
    ) -> ContinuityCompilationDraft:
        draft = original_continuity_create(service, shot_id)
        proposal = accepted_current_proposal(AutomationProposalType.CONTINUITY, draft.shot_id)
        if proposal is None:
            return draft
        continuity = draft.continuity_value()
        continuity.update(proposal.payload)
        updated = replace(
            draft,
            previous_shot_id=str(continuity.get("previous_shot_id", draft.previous_shot_id)),
            continuity=continuity,
            production_notes=f"Seeded from accepted automation proposal {proposal.proposal_id}.",
        )
        service._replace(updated)
        return updated

    ActionPerformanceCompilerService.create_from_current_package = action_create  # type: ignore[method-assign]
    GovernedCameraPlanningService.suggested_plan = camera_suggested  # type: ignore[method-assign]
    GovernedLightingPlanningService.suggested_plan = lighting_suggested  # type: ignore[method-assign]
    GovernedEnvironmentPlanningService.suggested_plan = environment_suggested  # type: ignore[method-assign]
    ContinuityCompilerService.create_from_current_package = continuity_create  # type: ignore[method-assign]
    _INSTALLED = True
