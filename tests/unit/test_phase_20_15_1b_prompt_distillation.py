from __future__ import annotations

from vscs.application.production_execution.prompt_distillation import (
    ProductionPromptDistillationService,
)


def _production() -> dict[str, object]:
    return {
        "shot": {
            "title": "Nine Days in Xorix Orbit",
            "production_objective": (
                "Show the Iron Horizon bridge with Xorix visible, Sandra at the control "
                "station and Commander James Spence present."
            ),
            "required_action": (
                "Sandra looks up from the control station and reports something unusual to James."
            ),
            "dialogue_requirement": (
                "Sandra must report to James: Commander, I have something unusual."
            ),
            "continuity_in": "The Iron Horizon is in orbit before any anomaly is known.",
            "continuity_out": "James is attending to Sandra's report.",
            "shot_constraints": [
                "Keep the setting on the Iron Horizon bridge.",
                "Do not imply any threat has been confirmed.",
            ],
        },
        "action_performance": {
            "temporal_narrative": (
                "Sandra looks up from her control station and reports something unusual to James."
            ),
            "spoken_content": "Sandra: Commander, I have something unusual.",
        },
        "assets": [
            {
                "asset_id": "CAP-CHR-001",
                "role": "Commander James Spence",
                "category": "character",
            },
            {
                "asset_id": "CAP-CHR-003",
                "role": "Sandra Crawford",
                "category": "character",
            },
            {"asset_id": "CAP-PLN-002", "role": "Xorix", "category": "planet"},
        ],
        "camera": {
            "shot_size": "medium_close",
            "angle": "eye_level",
            "focal_length_mm": 50,
            "lens_family": "normal",
            "movement": "static",
            "composition": "preserve eye-line and natural headroom",
        },
        "lighting": {
            "lighting_intent": "low_key",
            "key_direction": "side",
            "color_temperature_k": 4300,
            "subject_readability": "maintain natural facial readability",
        },
        "environment": {
            "environment_context": "orbital_space",
            "atmosphere_state": "vacuum",
            "environment_constraints": [
                "Do not add atmospheric haze, clouds, wind or aerodynamic effects in vacuum."
            ],
        },
        "continuity": {
            "opening_state": "The Iron Horizon is in orbit before any anomaly is known.",
            "closing_state": "James is attending to Sandra's report.",
        },
        "style": {},
        "dialogue": [],
    }


def test_distills_structured_authority_into_clean_cinematic_prompt() -> None:
    raw = (
        'SHOT: {"title": "Nine Days in Xorix Orbit"}\n'
        'ACTION & PERFORMANCE: {"spoken_content": "Commander"}\n'
        'ASSETS: [{"asset_id": "CAP-CHR-001"}]'
    )

    distilled = ProductionPromptDistillationService().distill(
        _production(),
        universal_text=raw,
        fps=24,
        duration_seconds=22,
    )

    assert "SHOT:" not in distilled.positive
    assert "ASSETS:" not in distilled.positive
    assert '{"' not in distilled.positive
    assert "Commander James Spence" in distilled.positive
    assert "Sandra Crawford" in distilled.positive
    assert "Xorix" in distilled.positive
    assert "medium close" in distilled.positive
    assert "50 mm" in distilled.positive
    assert "low key" in distilled.positive
    assert "4300 K" in distilled.positive
    assert "22 seconds at 24 fps" in distilled.positive
    assert "Commander, I have something unusual" in distilled.positive
    assert "wrong canonical asset identity" in distilled.negative


def test_distillation_preserves_governed_constraints_without_json_dump() -> None:
    distilled = ProductionPromptDistillationService().distill(
        _production(),
        universal_text="Structured authority follows elsewhere.",
        fps=24,
        duration_seconds=22,
    )

    assert "Keep the setting on the Iron Horizon bridge." in distilled.positive
    assert "Do not imply any threat has been confirmed." in distilled.positive
    assert "Do not add atmospheric haze" in distilled.positive
    assert distilled.shot_summary.startswith("Show the Iron Horizon bridge")
