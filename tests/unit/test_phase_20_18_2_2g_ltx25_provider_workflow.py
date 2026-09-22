from __future__ import annotations

import json
from pathlib import Path

from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    LTX25GovernedKeyframeDeploymentAssurance,
)

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / "resources" / "workflows"


def test_candidate_c_api_workflow_passes_static_deployment_assurance() -> None:
    assert LTX25GovernedKeyframeDeploymentAssurance(WORKFLOW_ROOT).inspect() == ()


def test_candidate_c_api_workflow_uses_one_keyframe_and_no_ingredients_guides() -> None:
    raw = json.loads(
        (WORKFLOW_ROOT / "workflows" / "ltx25_i2v_keyframe_v1_api.json").read_text(encoding="utf-8")
    )
    types = [node["class_type"] for node in raw.values()]

    assert types.count("VSCSLTX25GovernedKeyframePackageLoaderV1") == 1
    assert types.count("LTXVImgToVideoInplace") == 1
    assert "LTXAddVideoICLoRAGuide" not in types
    assert "VSCSMultiReferenceResolverV721" not in types
    assert raw["13"]["inputs"]["image"] == ["9", 0]
    assert raw["6"]["inputs"]["text"] == ["1", 1]
    assert raw["23"]["inputs"]["governed_frame_count"] == ["1", 6]
    assert raw["2"]["inputs"]["vae_name"] == r"ltx2.5\ltx-2.5-audio-vae-bf16.safetensors"
    assert raw["3"]["inputs"]["vae_name"] == (r"ltx2.5\ltx-2.5-video-vae-conv-bf16.safetensors")
    assert raw["4"]["inputs"]["unet_name"] == (
        r"ltx2.5\ltx-2.5-22b-distilled-transformer-bf16.safetensors"
    )
    assert raw["5"]["inputs"]["clip_name"] == (
        r"ltx2.5\gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"
    )


def test_candidate_c_manifest_declares_ltx25_governed_keyframe() -> None:
    manifest = json.loads(
        (WORKFLOW_ROOT / "manifests" / "ltx25_i2v_keyframe_v1.json").read_text(encoding="utf-8")
    )
    assert manifest["metadata"]["workflow_id"] == "ltx25_i2v_keyframe_v1"
    assert "governed_keyframe" in manifest["capabilities"]
    assert dict(manifest["extra"])["rebaseline_candidate"] == "C"
    assert dict(manifest["extra"])["combined_identity_video_reference"] == "disabled"


def test_candidate_c_provider_frame_adapter_preserves_six_second_governed_output() -> None:
    from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
        CurrentAuthorityLTX25GovernedKeyframeCompilationService,
    )

    assert CurrentAuthorityLTX25GovernedKeyframeCompilationService._provider_frame_count(144) == 145
    assert CurrentAuthorityLTX25GovernedKeyframeCompilationService._provider_frame_count(145) == 145
