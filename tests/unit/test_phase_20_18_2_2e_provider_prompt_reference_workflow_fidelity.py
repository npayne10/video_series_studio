"""Phase 20.18.2.2e provider prompt/reference/workflow fidelity regressions."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.application.acpp.reference_roles import ReferencePriority
from vscs.application.governed_reference_suitability_review import (
    suggested_reference_priority,
)
from vscs.application.production_execution.provider_prompt import (
    ProductionProviderPromptCompiler,
)
from vscs.application.rendering.workflows import (
    WorkflowCompatibilityValidator,
    WorkflowRegistry,
)
from vscs.application.story.asset_resolver import GovernedAssetResolutionService
from vscs.domain.assets import AssetCategory
from vscs.infrastructure.production_execution.ltx23_v721_backend import (
    LocalLTX23V721ProductionPackageCompilationService,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
)
from vscs.infrastructure.production_execution.segmented_backend import (
    SegmentedLTX23V721ProductionPackageCompilationService,
)
from vscs.infrastructure.rendering import ComfyUIWorkflowCompiler
from vscs.infrastructure.rendering.comfyui_production import (
    ProductionPackageComfyUIAdapter,
)


def test_structured_provider_prompt_excludes_governance_json_and_routes_negative_intent() -> None:
    production = {
        "shot": {
            "production_objective": (
                "Show the Iron Horizon bridge with Xorix visible on the forward display, "
                "Sandra Crawford at the control station, and Commander James Spence present."
            ),
            "required_action": (
                "Sandra Crawford notices an unusual reading and looks toward Commander James "
                "Spence. End before Sandra speaks. Do not spend this shot on a close reaction "
                "or insert."
            ),
            "shot_constraints": [
                "Keep the setting on the Iron Horizon bridge.",
                "Do not introduce additional named bridge officers.",
                "Hardware-aware Shot runtime must not exceed 7 seconds.",
            ],
        },
        "action_performance": {
            "temporal_narrative": (
                "Sandra Crawford notices an unusual reading and looks toward Commander James Spence."
            ),
            "performance_direction": "",
            "opening_state": "The Iron Horizon is already in Xorix orbit.",
            "closing_state": "Sandra is ready to report the reading.",
        },
        "camera": {
            "shot_size": "wide",
            "angle": "eye_level",
            "focal_length_mm": 28,
            "movement": "static",
            "composition": "prioritise readable spatial geography and subject placement",
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
            "environmental_motion": "no environmental motion beyond established system effects",
            "environment_constraints": [
                "Do not invent environmental physics or atmospheric properties."
            ],
        },
        "continuity": {
            "opening_state": "The Iron Horizon is already in Xorix orbit.",
            "closing_state": "Sandra is ready to report the reading.",
        },
        "style": {
            "negative_constraints": ["avoid fantasy glow"],
            "negative_prompt": (
                "generated speech, invented dialogue, unscripted voice, identity swap, "
                "duplicated character, merged identity, contact sheet, split screen, "
                "tiled references"
            ),
        },
        "assets": [
            {
                "asset_id": "CAP-CHR-001",
                "category": "character",
                "canonical_reference": r"assets\characters\CAP-CHR-001.png",
                "dependency_checksum": "deadbeef",
            },
            {
                "asset_id": "CAP-CHR-003",
                "category": "character",
                "canonical_reference": r"assets\characters\CAP-CHR-003.png",
                "dependency_checksum": "feedface",
            },
        ],
    }

    prompt = ProductionProviderPromptCompiler().compile(production)

    assert "Iron Horizon bridge" in prompt.positive_prompt
    assert "Xorix visible" in prompt.positive_prompt
    assert "Camera: wide shot; eye level angle; 28 mm lens; static camera movement" in (
        prompt.positive_prompt
    )
    assert "End before Sandra speaks." in prompt.positive_prompt
    assert "Do not spend this shot on a close reaction or insert." not in prompt.positive_prompt
    assert "Do not spend this shot on a close reaction or insert." in prompt.negative_prompt
    assert "Do not introduce additional named bridge officers." in prompt.negative_prompt
    assert "extra people" in prompt.negative_prompt
    assert "additional bridge crew" in prompt.negative_prompt
    assert "additional officers" in prompt.negative_prompt
    assert "third person" in prompt.negative_prompt
    assert prompt.negative_prompt.casefold().count("generated speech") == 1
    assert prompt.negative_prompt.casefold().count("invented dialogue") == 1
    assert prompt.negative_prompt.casefold().count("identity swap") == 1
    assert "avoid fantasy glow" in prompt.negative_prompt
    assert "asset_id" not in prompt.positive_prompt
    assert "dependency_checksum" not in prompt.positive_prompt
    assert r"assets\characters" not in prompt.positive_prompt
    assert len(prompt.positive_prompt) < 3000


def test_generic_bridge_name_requires_matching_location_scope() -> None:
    service = object.__new__(GovernedAssetResolutionService)
    mauritania_bridge = SimpleNamespace(
        asset_id="CAP-LOC-008",
        name="Bridge",
        category=AssetCategory.LOCATION,
        description="Mauritania command deck",
        tags=("xpd:subcategory=Mauritania",),
    )

    wrong_context = service._normalize_text(
        "Establish the Iron Horizon bridge with Xorix visible on the forward display."
    )
    correct_context = service._normalize_text(
        "Establish the Mauritania bridge while the carrier remains in orbit."
    )

    assert service._asset_evidence(mauritania_bridge, wrong_context) is None
    assert service._asset_evidence(mauritania_bridge, correct_context) is not None


def test_visible_planet_is_required_reference_authority() -> None:
    assert suggested_reference_priority("planet", "Visible Planet") is ReferencePriority.REQUIRED


def test_ltx_visual_fidelity_blocks_shot_critical_reference_dropped_by_capacity() -> None:
    plan = {
        "provider_multi_reference": {
            "references": [
                {"asset_id": "CAP-CHR-001"},
                {"asset_id": "CAP-CHR-003"},
                {"asset_id": "CAP-LOC-IRON-HORIZON"},
            ]
        }
    }
    authority = {
        "assets": [
            {"asset_id": "CAP-CHR-001", "category": "character", "role": "Supporting Character"},
            {"asset_id": "CAP-CHR-003", "category": "character", "role": "Supporting Character"},
            {"asset_id": "CAP-LOC-IRON-HORIZON", "category": "location", "role": "Location"},
            {"asset_id": "CAP-PLN-002", "category": "planet", "role": "Visible Planet"},
            {"asset_id": "CAP-SHP-002", "category": "ship", "role": "Vehicle/Ship"},
        ]
    }

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match=r"PROVIDER_VISUAL_AUTHORITY_DROPPED.*CAP-PLN-002",
    ):
        LocalLTX23V721ProductionPackageCompilationService._require_provider_visual_fidelity(
            plan, authority
        )


def test_ltx_visual_fidelity_accepts_composite_reference_coverage() -> None:
    plan = {
        "provider_multi_reference": {
            "references": [
                {"asset_id": "CAP-CHR-001"},
                {"asset_id": "CAP-CHR-003"},
                {
                    "asset_id": "CAP-LOC-IRON-HORIZON",
                    "contains_environments": ["CAP-PLN-002"],
                },
            ]
        }
    }
    authority = {
        "assets": [
            {"asset_id": "CAP-CHR-001", "category": "character", "role": "Supporting Character"},
            {"asset_id": "CAP-CHR-003", "category": "character", "role": "Supporting Character"},
            {"asset_id": "CAP-LOC-IRON-HORIZON", "category": "location", "role": "Location"},
            {"asset_id": "CAP-PLN-002", "category": "planet", "role": "Visible Planet"},
        ]
    }

    LocalLTX23V721ProductionPackageCompilationService._require_provider_visual_fidelity(
        plan, authority
    )

    contract = plan["provider_multi_reference"]
    assert contract["required_visual_asset_ids"] == [
        "CAP-CHR-001",
        "CAP-CHR-003",
        "CAP-LOC-IRON-HORIZON",
        "CAP-PLN-002",
    ]
    assert "CAP-PLN-002" in contract["covered_visual_asset_ids"]


def test_submission_audit_persists_exact_api_payload_and_provider_contract(
    tmp_path: Path,
) -> None:
    package = tmp_path / "compiled.json"
    package.write_text(
        json.dumps(
            {
                "_vscs_manifest": {
                    "package_fingerprint": "package-fingerprint-123456",
                    "authority_fingerprint": "authority-fingerprint",
                    "source_package_id": "PP-SHT-001",
                },
                "positive_prompt": "Wide static Iron Horizon bridge establishing shot.",
                "negative_prompt": "identity swap",
                "provider_prompt_contract": {
                    "schema_version": "1.0",
                    "compiler": "structured-authority-v1",
                },
                "width": 1280,
                "height": 720,
                "frame_count": 144,
                "fps": 24,
                "seed": 42,
                "reference_plan": {
                    "provider_multi_reference": {
                        "mode": "ltx_ingredients_iclora",
                        "references": [
                            {
                                "asset_id": "CAP-CHR-001",
                                "conditioning_mode": "attention_only",
                                "frame_idx": -1,
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    adapter = ProductionPackageComfyUIAdapter(
        WorkflowRegistry(),
        WorkflowCompatibilityValidator(),
        ComfyUIWorkflowCompiler(tmp_path),
        submission_audit_directory=tmp_path / "audit",
    )
    request = SimpleNamespace(
        request_id="REQ-SHT-001",
        production_id="XORIX",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="SHT-001",
        workflow_id="ltx23_production_v1",
        quality_level=SimpleNamespace(value="production"),
    )
    payload = {
        "prompt": {
            "9": {
                "class_type": "LTXAddVideoICLoRAGuide",
                "inputs": {
                    "frame_idx": -1,
                    "image": ["108", 0],
                    "strength": ["108", 3],
                },
                "_meta": {"title": "Governed IC-LoRA Guide — Primary Identity"},
            }
        },
        "client_id": "REQ-SHT-001",
    }

    adapter._persist_submission_audit(request, payload, str(package))

    files = tuple((tmp_path / "audit").glob("*.json"))
    assert len(files) == 1
    audit = json.loads(files[0].read_text(encoding="utf-8"))
    assert audit["api_payload"] == payload
    assert audit["provider_prompt"]["positive"].startswith("Wide static")
    assert audit["production_package"]["package_fingerprint"] == "package-fingerprint-123456"
    assert audit["workflow"]["guide_nodes"][0]["frame_idx"] == -1
    assert audit["reference_contract"]["references"][0]["conditioning_mode"] == "attention_only"


def test_provider_role_authority_deduplicates_existing_audio_negatives() -> None:
    content = {
        "positive_prompt": "Wide Iron Horizon bridge establishing shot.",
        "negative_prompt": (
            "generated speech; invented dialogue; identity swap; extra people; "
            "Do not introduce additional named bridge officers."
        ),
        "reference_plan": {
            "provider_multi_reference": {
                "references": [
                    {
                        "role": "group_identity",
                        "label": "James Spence + Sandra Crawford",
                    }
                ]
            }
        },
        "acpp": {
            "prompts": {
                "positive": "Wide Iron Horizon bridge establishing shot.",
                "negative": "stale",
            },
            "generation": {"audio_mode": "generated_reference"},
        },
    }

    result = SegmentedLTX23V721ProductionPackageCompilationService._apply_provider_role_authority(
        content
    )

    negative = str(result["negative_prompt"])
    assert negative.casefold().count("generated speech") == 1
    assert negative.casefold().count("invented dialogue") == 1
    assert negative.casefold().count("identity swap") == 1
    assert negative.casefold().count("unscripted voice") == 1
    assert negative.casefold().count("duplicated character") == 1
    assert negative.casefold().count("merged identity") == 1
    assert negative.casefold().count("contact sheet") == 1
    assert negative.casefold().count("split screen") == 1
    assert negative.casefold().count("tiled references") == 1
    assert "extra people" in negative
    assert result["acpp"]["prompts"]["negative"] == negative
    assert result["acpp"]["generation"]["audio_mode"] == "silent_visual_authority"
