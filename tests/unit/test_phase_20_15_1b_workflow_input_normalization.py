from __future__ import annotations

import json
from pathlib import Path

from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.infrastructure.production_execution.provider_ready_package import (
    ProviderReadyProductionPackageResolver,
)


def _compiled() -> CompiledProductionPackage:
    production = {
        "shot": {
            "production_objective": "Show James and Sandra on the Iron Horizon bridge.",
            "required_action": "Sandra reports something unusual to James.",
            "target_runtime_seconds": 22,
        },
        "assets": [],
        "camera": {"shot_size": "medium_close", "movement": "static"},
        "lighting": {"lighting_intent": "low_key"},
        "environment": {"environment_context": "orbital_space"},
        "action_performance": {"spoken_content": "Commander, I have something unusual."},
        "continuity": {},
        "style": {},
        "dialogue": [],
        "effects": [],
    }
    return CompiledProductionPackage(
        task_id="PT-001",
        production_id="TSR2",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        profile="production",
        authority_id="AUTH-001",
        authority_revision=1,
        authority_fingerprint="authority",
        approved_by="human",
        source_package_id="PP-001",
        source_package_fingerprint="source",
        source_schema_version="1.0",
        universal_text="SHOT: {raw structured authority}",
        positive_prompt=(
            "Create one continuous uninterrupted cinematic shot. Show James and Sandra on the "
            "Iron Horizon bridge."
        ),
        negative_prompt="wrong canonical asset identity; AI artifacts",
        previous_approved_final_frame=None,
        filename_prefix="TSR2/EP-001/PT-001",
        width=1280,
        height=720,
        frame_count=528,
        frames_per_second=24,
        duration_seconds=22.0,
        cfg=1.0,
        ic_lora_strength=1.0,
        seed=123456,
        composition_plan={"shot_id": "SHT-001"},
        production_authority=production,
        package_fingerprint="compiled",
    )


def test_provider_ready_package_exposes_normalized_workflow_inputs(tmp_path: Path) -> None:
    resolved = ProviderReadyProductionPackageResolver(tmp_path).resolve(_compiled())
    workflow = resolved["workflow_inputs"]

    assert workflow["compiled_positive_prompt"] == resolved["prompts"]["positive"]
    assert workflow["compiled_negative_prompt"] == resolved["prompts"]["negative"]
    assert workflow["seed"] == 123456
    assert workflow["fps"] == 24
    assert workflow["frame_count"] == 528
    assert workflow["width"] == 1280
    assert workflow["height"] == 720
    assert workflow["filename_prefix"] == "TSR2/EP-001/production/PT-001_production"
    assert workflow["continuity_image_path"] == ""
    assert workflow["shot_summary"] == "Show James and Sandra on the Iron Horizon bridge."
    assert "SHOT:" not in workflow["compiled_positive_prompt"]

    reference_plan = json.loads(workflow["reference_plan_json"])
    composition_plan = json.loads(workflow["composition_plan_json"])
    assert reference_plan["mode"] == "identity_first_minimal"
    assert composition_plan["provider_ready"] is True


def test_prompt_contract_declares_structured_authority_separate_from_text_conditioning(
    tmp_path: Path,
) -> None:
    resolved = ProviderReadyProductionPackageResolver(tmp_path).resolve(_compiled())
    contract = resolved["validation_contract"]["prompt_contract"]

    assert contract["structured_authority_is_source_of_truth"] is True
    assert contract["raw_json_in_text_conditioning"] is False
    assert contract["workflow_inputs_are_provider_interface"] is True
    assert contract["legacy_v714_top_level_fields_are_compatibility_projections"] is True
