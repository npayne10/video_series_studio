from __future__ import annotations

from PySide6.QtWidgets import QLabel, QScrollArea

from vscs.application.story import (
    AtmosphereState,
    EnvironmentContext,
    EnvironmentPlan,
    ShotPlan,
    ShotPlanStatus,
    TimeContext,
    WeatherState,
)
from vscs.presentation.widgets.governed_environment_planner import (
    EnvironmentPlanEditorDialog,
)


class FakeEnvironmentService:
    def setting_requirement(self, _shot_id: str) -> str:
        return "Xorix orbit"


def _shot() -> ShotPlan:
    return ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id="EP-001-SCN-001",
        sequence_number=1,
        title="Orbital arrival",
        narrative_purpose="Establish Xorix",
        production_objective="Show physically credible orbital scale",
        target_runtime_seconds=12,
        required_action="Ship crosses the frame in stable orbit",
        scene_contract_hash="scene",
        status=ShotPlanStatus.READY,
    )


def _plan() -> EnvironmentPlan:
    return EnvironmentPlan(
        environment_plan_id="EP-001-SCN-001-SHT-001-ENV",
        shot_id="EP-001-SCN-001-SHT-001",
        environment_context=EnvironmentContext.ORBITAL_SPACE,
        time_context=TimeContext.NOT_APPLICABLE,
        atmosphere_state=AtmosphereState.VACUUM,
        weather_state=WeatherState.NONE,
        gravity_m_s2=None,
        pressure_kpa=0.0,
        temperature_c=None,
        visibility_m=None,
        surface_state="vacuum environment",
        environmental_motion="orbital motion only",
        continuity_notes="Preserve orbital geography",
        environment_constraints=("No atmospheric haze",),
    )


def test_environment_editor_is_resizable_scrollable_and_specialist_scoped(qtbot) -> None:
    dialog = EnvironmentPlanEditorDialog(
        FakeEnvironmentService(),  # type: ignore[arg-type]
        _shot(),
        _plan(),
    )
    qtbot.addWidget(dialog)

    scroll = dialog.findChild(QScrollArea)
    assert scroll is not None
    assert dialog.minimumWidth() <= 680
    assert dialog.minimumHeight() <= 520
    rendered = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "unknown physics" in rendered.lower()
    assert "Camera framing" in rendered
    assert "lighting design" in rendered
    assert "renderer settings" in rendered


def test_environment_editor_round_trips_unknown_and_structured_physical_state(qtbot) -> None:
    dialog = EnvironmentPlanEditorDialog(
        FakeEnvironmentService(),  # type: ignore[arg-type]
        _shot(),
        _plan(),
    )
    qtbot.addWidget(dialog)

    values = dialog.values()

    assert values.environment_context is EnvironmentContext.ORBITAL_SPACE
    assert values.time_context is TimeContext.NOT_APPLICABLE
    assert values.atmosphere_state is AtmosphereState.VACUUM
    assert values.weather_state is WeatherState.NONE
    assert values.gravity_m_s2 is None
    assert values.pressure_kpa == 0.0
    assert values.temperature_c is None
    assert values.environment_constraints == ("No atmospheric haze",)
