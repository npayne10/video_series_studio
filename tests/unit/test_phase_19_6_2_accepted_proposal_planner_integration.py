from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from vscs.application.automation.accepted_proposal_integration import (
    _camera_from_proposal,
    _environment_from_proposal,
    _lighting_from_proposal,
    accepted_current_proposal,
    install_accepted_proposal_consumption,
)
from vscs.application.automation.contracts import (
    AutomationProposal,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from vscs.application.automation.service import AutomationProposalService
from vscs.application.story import (
    AtmosphereState,
    CameraAngle,
    CameraMovement,
    CameraPlan,
    EnvironmentContext,
    EnvironmentPlan,
    ExposureIntent,
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


def _proposal(
    proposal_type: AutomationProposalType,
    payload: dict[str, Any],
    *,
    revision: str = "rev-current",
    proposal_id: str | None = None,
) -> AutomationProposal:
    identifier = proposal_id or f"AUT-{proposal_type.value.upper()}-TEST"
    return AutomationProposal(
        proposal_id=identifier,
        proposal_type=proposal_type,
        target_id="EP-001-SC-001-SHT-001",
        payload=payload,
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.AI_INFERENCE,
            source_story_id="STORY-001",
            source_revision=revision,
            source_scope="test",
            provider="openai",
            model="test-model",
        ),
        status=AutomationProposalStatus.ACCEPTED,
        reviewed_by="Neill",
        accepted_by="Neill",
    )


def test_current_revision_selection_ignores_stale_accepted_proposal(tmp_path: Any) -> None:
    projects = SimpleNamespace(project_directory=tmp_path)
    service = AutomationProposalService(projects)
    install_accepted_proposal_consumption(service)
    stale = _proposal(
        AutomationProposalType.CAMERA,
        {"composition": "stale"},
        revision="rev-old",
        proposal_id="AUT-CAMERA-OLD",
    )
    current = _proposal(
        AutomationProposalType.CAMERA,
        {"composition": "current"},
        proposal_id="AUT-CAMERA-CURRENT",
    )
    service.save(stale)
    service.save(current)
    automation_dir = tmp_path / "automation"
    automation_dir.mkdir(parents=True, exist_ok=True)
    (automation_dir / "automation_compilation.json").write_text(
        json.dumps({"report": {"source_revision": "rev-current"}}),
        encoding="utf-8",
    )

    selected = accepted_current_proposal(
        AutomationProposalType.CAMERA,
        "EP-001-SC-001-SHT-001",
    )

    assert selected is not None
    assert selected.proposal_id == "AUT-CAMERA-CURRENT"


def test_camera_mapping_preserves_accepted_ai_fields() -> None:
    base = CameraPlan(
        camera_plan_id="CAM-001",
        shot_id="EP-001-SC-001-SHT-001",
        shot_size=ShotSize.MEDIUM,
        angle=CameraAngle.EYE_LEVEL,
        movement=CameraMovement.STATIC,
        lens_family=LensFamily.NORMAL,
        focal_length_mm=50,
        camera_height_m=1.6,
        screen_direction=ScreenDirection.PRESERVE_PREVIOUS,
        composition="base",
        focus_strategy="base",
        shot_contract_hash="shot-hash",
        asset_context_hash="asset-hash",
    )
    proposal = _proposal(
        AutomationProposalType.CAMERA,
        {
            "shot_size": "wide",
            "angle": "eye_level",
            "movement": "push_in",
            "lens_family": "wide",
            "focal_length_mm": 32,
            "camera_height_m": 1.55,
            "screen_direction": "neutral",
            "composition": "AI composition",
            "focus_strategy": "AI focus",
            "movement_notes": "Slow push-in",
            "continuity_notes": "Keep Xorix visible",
            "camera_constraints": ["Preserve bridge geometry"],
            "camera_profile_asset_id": "",
        },
    )

    mapped = _camera_from_proposal(base, proposal)

    assert mapped.shot_size is ShotSize.WIDE
    assert mapped.movement is CameraMovement.PUSH_IN
    assert mapped.focal_length_mm == 32
    assert mapped.camera_height_m == pytest.approx(1.55)
    assert mapped.composition == "AI composition"
    assert mapped.focus_strategy == "AI focus"
    assert mapped.camera_constraints == ("Preserve bridge geometry",)
    assert mapped.shot_contract_hash == "shot-hash"
    assert mapped.asset_context_hash == "asset-hash"


def test_lighting_mapping_preserves_accepted_ai_fields() -> None:
    base = LightingPlan(
        lighting_plan_id="LGT-001",
        shot_id="EP-001-SC-001-SHT-001",
        lighting_intent=LightingIntent.PRACTICAL_MOTIVATED,
        key_direction=KeyDirection.MOTIVATED,
        key_quality=LightQuality.SOFT,
        color_temperature_k=4300,
        fill_level_percent=40,
        exposure_intent=ExposureIntent.BALANCED,
        source_strategy="base",
        shadow_strategy="base",
        subject_readability="base",
        shot_contract_hash="shot-hash",
        asset_context_hash="asset-hash",
        camera_context_hash="camera-hash",
    )
    proposal = _proposal(
        AutomationProposalType.LIGHTING,
        {
            "lighting_intent": "low_key",
            "key_direction": "side",
            "key_quality": "medium",
            "color_temperature_k": 4100,
            "fill_level_percent": 22,
            "exposure_intent": "protect_highlights",
            "source_strategy": "AI source",
            "shadow_strategy": "AI shadows",
            "subject_readability": "AI readability",
            "separation_strategy": "AI separation",
            "continuity_notes": "Maintain practicals",
            "lighting_constraints": ["No decorative glow"],
            "lighting_profile_asset_id": "",
        },
    )

    mapped = _lighting_from_proposal(base, proposal)

    assert mapped.lighting_intent is LightingIntent.LOW_KEY
    assert mapped.key_direction is KeyDirection.SIDE
    assert mapped.color_temperature_k == 4100
    assert mapped.fill_level_percent == 22
    assert mapped.source_strategy == "AI source"
    assert mapped.lighting_constraints == ("No decorative glow",)
    assert mapped.camera_context_hash == "camera-hash"


def test_environment_mapping_preserves_accepted_ai_fields() -> None:
    base = EnvironmentPlan(
        environment_plan_id="ENV-001",
        shot_id="EP-001-SC-001-SHT-001",
        environment_context=EnvironmentContext.INTERIOR,
        time_context=TimeContext.ARTIFICIAL_CYCLE,
        atmosphere_state=AtmosphereState.CONTROLLED,
        weather_state=WeatherState.NONE,
        gravity_m_s2=None,
        pressure_kpa=None,
        temperature_c=None,
        visibility_m=None,
        surface_state="base",
        environmental_motion="base",
        shot_contract_hash="shot-hash",
        asset_context_hash="asset-hash",
        camera_context_hash="camera-hash",
        lighting_context_hash="lighting-hash",
    )
    proposal = _proposal(
        AutomationProposalType.ENVIRONMENT,
        {
            "environment_context": "interior",
            "time_context": "artificial_cycle",
            "atmosphere_state": "controlled",
            "weather_state": "none",
            "gravity_m_s2": 9.81,
            "pressure_kpa": 101.3,
            "temperature_c": 21.0,
            "visibility_m": 100.0,
            "surface_state": "AI surface",
            "environmental_motion": "AI motion",
            "hazard_notes": "None",
            "continuity_notes": "Preserve bridge state",
            "environment_constraints": ["No atmospheric effects"],
        },
    )

    mapped = _environment_from_proposal(base, proposal)

    assert mapped.gravity_m_s2 == pytest.approx(9.81)
    assert mapped.pressure_kpa == pytest.approx(101.3)
    assert mapped.surface_state == "AI surface"
    assert mapped.environmental_motion == "AI motion"
    assert mapped.environment_constraints == ("No atmospheric effects",)
    assert mapped.lighting_context_hash == "lighting-hash"


def test_mapping_keeps_draft_governance_state() -> None:
    base = CameraPlan(
        camera_plan_id="CAM-001",
        shot_id="EP-001-SC-001-SHT-001",
        shot_size=ShotSize.MEDIUM,
        angle=CameraAngle.EYE_LEVEL,
        movement=CameraMovement.STATIC,
        lens_family=LensFamily.NORMAL,
        focal_length_mm=50,
        camera_height_m=1.6,
        screen_direction=ScreenDirection.PRESERVE_PREVIOUS,
        composition="base",
        focus_strategy="base",
    )
    proposal = _proposal(
        AutomationProposalType.CAMERA,
        {
            "shot_size": "medium",
            "angle": "eye_level",
            "movement": "static",
            "lens_family": "normal",
            "focal_length_mm": 50,
            "camera_height_m": 1.6,
            "screen_direction": "neutral",
            "composition": "accepted",
            "focus_strategy": "accepted",
        },
    )

    mapped = _camera_from_proposal(replace(base), proposal)

    assert mapped.status == base.status
