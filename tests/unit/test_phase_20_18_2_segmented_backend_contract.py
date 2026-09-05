from __future__ import annotations

from vscs.infrastructure.production_execution.segmented_backend import (
    LocalComfyUIProductionExecutionBackend,
    SegmentedLTX23V721ProductionPackageCompilationService,
)


def test_segmented_backend_exposes_profile_scoped_start_and_reconcile() -> None:
    assert "start_for_profile" in LocalComfyUIProductionExecutionBackend.__dict__
    assert "reconcile_for_profile" in LocalComfyUIProductionExecutionBackend.__dict__


def test_segmented_package_compiler_remains_current_authority_extension() -> None:
    assert "_comfyui_payload" in SegmentedLTX23V721ProductionPackageCompilationService.__dict__


def test_segmented_package_enforces_reference_roles_and_no_generated_dialogue() -> None:
    content = {
        "positive_prompt": "Sandra reports unusual sensor data to James.",
        "negative_prompt": "identity drift",
        "acpp": {
            "generation": {"audio_mode": "generated_reference"},
            "prompts": {
                "positive": "Sandra reports unusual sensor data to James.",
                "negative": "identity drift",
            },
        },
        "reference_plan": {
            "provider_multi_reference": {
                "references": [
                    {
                        "role": "primary_identity",
                        "label": "Commander James Spence approved identity",
                    },
                    {
                        "role": "secondary_identity",
                        "label": "Sandra Crawford approved identity",
                    },
                    {
                        "role": "environment_reference",
                        "label": "Xorix approved environment",
                    },
                ]
            }
        },
    }

    result = SegmentedLTX23V721ProductionPackageCompilationService._apply_provider_role_authority(
        content
    )

    assert "Commander James Spence approved identity" in result["positive_prompt"]
    assert result["shot_prompt"] == result["positive_prompt"]
    assert "Sandra Crawford approved identity" in result["positive_prompt"]
    assert "Xorix approved environment" in result["positive_prompt"]
    assert "Do not invent spoken dialogue or voices" in result["positive_prompt"]
    assert "generated speech" in result["negative_prompt"]
    assert result["acpp"]["generation"]["audio_mode"] == "silent_visual_authority"
    assert result["provider_dialogue_policy"]["mode"] == "no_generated_dialogue"
