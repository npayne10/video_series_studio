from __future__ import annotations

from PySide6.QtWidgets import QLabel, QScrollArea

from vscs.application.story import (
    ExposureIntent,
    KeyDirection,
    LightingIntent,
    LightingPlan,
    LightQuality,
    ShotPlan,
    ShotPlanStatus,
)
from vscs.presentation.widgets.governed_lighting_planner import LightingPlanEditorDialog


class FakeLightingService:
    def available_lighting_profiles(self):
        return ()


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


def _plan() -> LightingPlan:
    return LightingPlan(
        lighting_plan_id="EP-001-SCN-001-SHT-001-LGT",
        shot_id="EP-001-SCN-001-SHT-001",
        lighting_intent=LightingIntent.NATURALISTIC,
        key_direction=KeyDirection.SIDE,
        key_quality=LightQuality.HARD,
        color_temperature_k=5600,
        fill_level_percent=18,
        exposure_intent=ExposureIntent.PROTECT_HIGHLIGHTS,
        source_strategy="Use one physically motivated dominant source with restrained indirect fill",
        shadow_strategy="Preserve credible directional shadows",
        subject_readability="Keep essential spacecraft geometry readable",
        separation_strategy="Use restrained tonal separation",
        continuity_notes="Preserve source direction across adjacent shots",
        lighting_constraints=("No decorative glow",),
    )


def test_lighting_editor_is_resizable_scrollable_and_specialist_scoped(qtbot) -> None:
    dialog = LightingPlanEditorDialog(
        FakeLightingService(),  # type: ignore[arg-type]
        _shot(),
        _plan(),
    )
    qtbot.addWidget(dialog)

    scroll = dialog.findChild(QScrollArea)
    assert scroll is not None
    assert dialog.minimumWidth() <= 660
    assert dialog.minimumHeight() <= 520
    rendered = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "renderer settings" in rendered.lower()
    assert "Environment/weather/time-of-day" in rendered


def test_lighting_editor_round_trips_structured_lighting_values(qtbot) -> None:
    dialog = LightingPlanEditorDialog(
        FakeLightingService(),  # type: ignore[arg-type]
        _shot(),
        _plan(),
    )
    qtbot.addWidget(dialog)

    values = dialog.values()

    assert values.lighting_intent is LightingIntent.NATURALISTIC
    assert values.key_direction is KeyDirection.SIDE
    assert values.key_quality is LightQuality.HARD
    assert values.color_temperature_k == 5600
    assert values.fill_level_percent == 18
    assert values.exposure_intent is ExposureIntent.PROTECT_HIGHLIGHTS
    assert values.lighting_constraints == ("No decorative glow",)
