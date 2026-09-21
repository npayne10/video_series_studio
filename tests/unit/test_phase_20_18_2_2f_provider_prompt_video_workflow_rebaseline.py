"""Phase 20.18.2.2f provider prompt and video workflow rebaseline."""

from __future__ import annotations

from vscs.application.production_execution.provider_prompt import (
    ProductionProviderPromptCompiler,
)
from vscs.application.production_execution.video_workflow_rebaseline import (
    ProviderVideoCandidateId,
    provider_video_candidates,
    provider_video_rebaseline_contract,
)


def _sht001_authority() -> dict[str, object]:
    return {
        "shot": {
            "production_objective": (
                "Show the Iron Horizon bridge with Xorix visible on the forward display, "
                "Sandra Crawford at the control station, and Commander James Spence present."
            ),
            "required_action": (
                "Establish the full spatial relationship and initial state of the Iron Horizon "
                "bridge after nine days in the Xorix system. Xorix is visible on the forward "
                "display. Sandra Crawford is at her control station and notices an unusual "
                "reading. She looks up toward Commander James Spence, who remains focused on "
                "the forward display. End the shot before Sandra speaks. Do not spend this shot "
                "on a close reaction or insert."
            ),
            "shot_constraints": [
                "Keep the setting on the Iron Horizon bridge.",
                "Do not imply any threat has been confirmed.",
                "Do not introduce additional named bridge officers.",
                "Hardware-aware Shot runtime must not exceed 7 seconds.",
            ],
        },
        "action_performance": {
            "temporal_narrative": (
                "Establish the full spatial relationship and initial state of the Iron Horizon "
                "bridge after nine days in the Xorix system. Xorix is visible on the forward "
                "display. Sandra Crawford is at her control station and notices an unusual "
                "reading. She looks up toward Commander James Spence, who remains focused on "
                "the forward display. End the shot before Sandra speaks. Do not spend this shot "
                "on a close reaction or insert."
            ),
            "performance_direction": "",
        },
        "camera": {
            "shot_size": "wide",
            "angle": "eye_level",
            "focal_length_mm": 28,
            "movement": "static",
            "composition": "prioritise readable spatial geography, scale and subject placement",
            "camera_constraints": [],
        },
        "lighting": {
            "lighting_intent": "naturalistic",
            "color_temperature_k": 5600,
            "key_quality": "hard",
            "key_direction": "side",
            "fill_level_percent": 18,
            "lighting_constraints": [],
        },
        "environment": {
            "environment_context": "interior",
            "atmosphere_state": "controlled",
            "surface_state": "stable engineered interior surfaces",
            "environmental_motion": "no environmental motion beyond established ship systems",
            "environment_constraints": [
                "Do not invent environmental physics or atmospheric properties."
            ],
        },
        "style": {},
        "assets": [
            {"asset_id": "CAP-CHR-001", "category": "character"},
            {"asset_id": "CAP-CHR-003", "category": "character"},
            {"asset_id": "CAP-PLN-002", "category": "planet"},
            {"asset_id": "CAP-LOC-021", "category": "location"},
        ],
    }


def test_sht001_cinematic_prompt_is_short_literal_and_free_of_governance_prose() -> None:
    prompt = ProductionProviderPromptCompiler().compile(_sht001_authority())

    assert prompt.compiler == "cinematic-action-v2"
    assert prompt.positive_word_count <= 150
    assert "Exactly two people are visible throughout the shot." in prompt.positive_prompt
    assert "All other bridge stations remain empty." in prompt.positive_prompt
    assert "Sandra Crawford is at her control station" in prompt.positive_prompt
    assert "She looks up toward Commander James Spence" in prompt.positive_prompt
    assert "Xorix is visible on the forward display." in prompt.positive_prompt
    assert "GOVERNED REFERENCE ROLE AUTHORITY" not in prompt.positive_prompt
    assert "group_identity" not in prompt.positive_prompt
    assert "environment_reference" not in prompt.positive_prompt
    assert "CAP-" not in prompt.positive_prompt
    assert "provider" not in prompt.positive_prompt.casefold()


def test_sht001_motion_prompt_is_action_first_and_bounded() -> None:
    prompt = ProductionProviderPromptCompiler().compile(_sht001_authority())

    assert prompt.motion_word_count <= 90
    assert prompt.motion_prompt.startswith("Exactly two people are visible throughout the shot.")
    assert "Sandra Crawford is at her control station and notices an unusual reading." in (
        prompt.motion_prompt
    )
    assert "She looks up toward Commander James Spence" in prompt.motion_prompt
    assert "The camera remains locked in place throughout the shot." in prompt.motion_prompt
    assert "5600" not in prompt.motion_prompt
    assert "governed" not in prompt.motion_prompt.casefold()


def test_sht001_negative_prompt_retains_people_and_dialogue_safeguards() -> None:
    prompt = ProductionProviderPromptCompiler().compile(_sht001_authority())

    for safeguard in (
        "generated speech",
        "invented dialogue",
        "identity swap",
        "extra people",
        "background people",
        "additional bridge crew",
        "additional officers",
        "third person",
    ):
        assert safeguard in prompt.negative_prompt


def test_rebaseline_keeps_a_executable_and_c_preferred_fail_closed() -> None:
    candidates = provider_video_candidates()
    by_id = {item.candidate_id: item for item in candidates}

    assert by_id[ProviderVideoCandidateId.A_LTX23_INGREDIENTS].execution_ready is True
    assert by_id[ProviderVideoCandidateId.B_LTX23_I2V_KEYFRAME].execution_ready is False
    assert by_id[ProviderVideoCandidateId.C_LTX25_I2V_KEYFRAME].execution_ready is False
    assert by_id[ProviderVideoCandidateId.C_LTX25_I2V_KEYFRAME].preferred is True

    contract = provider_video_rebaseline_contract()
    assert contract["active_candidate"] == "A"
    assert contract["preferred_candidate"] == "C"
    assert contract["execution_policy"] == "only_execution_ready_candidate_may_submit"
    assert len(contract["visual_acceptance_criteria"]) == 15


def test_scene_prompt_omits_optional_detail_before_blocking_essential_action() -> None:
    authority = _sht001_authority()
    authority["lighting"] = {
        "lighting_intent": "naturalistic cinematic physically motivated practical illumination",
        "color_temperature_k": 5600,
        "key_quality": "hard directional controlled realistic motivated",
        "key_direction": "side with detailed motivated practical source geometry",
        "fill_level_percent": 18,
    }
    authority["style"] = {
        "declared_style": (
            "grounded engineered premium streaming hard science fiction with restrained "
            "production design and realistic materials"
        ),
        "declared_tone": (
            "quietly observational procedural controlled precise professional understated"
        ),
    }

    prompt = ProductionProviderPromptCompiler().compile(authority)

    assert prompt.positive_word_count <= 150
    assert "Sandra Crawford is at her control station" in prompt.positive_prompt
    assert "She looks up toward Commander James Spence" in prompt.positive_prompt
    assert prompt.omitted_optional_sections
