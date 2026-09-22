from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vscs.application.production_execution import (
    KEYFRAME_ACCEPTANCE_CRITERIA,
    GovernedShotKeyframe,
    GovernedShotKeyframeError,
    GovernedShotKeyframeStore,
    ProviderVideoCandidateId,
    provider_video_rebaseline_contract,
)

ROOT = Path(__file__).resolve().parents[2]
MANUAL = ROOT / "resources" / "workflows" / "manual"
WORKFLOW = MANUAL / "ltx25_candidate_c_governed_keyframe_i2v_manual.json"


def test_candidate_c_activates_only_from_governed_keyframe_authority() -> None:
    without = provider_video_rebaseline_contract(governed_keyframe_ready=False)
    with_keyframe = provider_video_rebaseline_contract(governed_keyframe_ready=True)

    assert without["active_candidate"] == ProviderVideoCandidateId.A_LTX23_INGREDIENTS.value
    assert with_keyframe["active_candidate"] == ProviderVideoCandidateId.C_LTX25_I2V_KEYFRAME.value
    assert (
        with_keyframe["preferred_candidate"] == ProviderVideoCandidateId.C_LTX25_I2V_KEYFRAME.value
    )
    assert with_keyframe["phase"] == "20.18.2.2g"


def test_governed_keyframe_is_checksum_pinned_and_fail_closed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    image = project / "sht001.png"
    image.write_bytes(b"governed-keyframe")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    record = GovernedShotKeyframe(
        shot_id="EP-001-SCN-001-SHT-001",
        image_path="sht001.png",
        image_sha256=digest,
        approved_by="Neill Payne",
        approved_at="2026-09-21T20:30:00+02:00",
        acceptance_criteria=KEYFRAME_ACCEPTANCE_CRITERIA,
    )
    store = GovernedShotKeyframeStore(project)

    saved = store.save(record)
    assert saved.approved

    image.write_bytes(b"changed-after-approval")
    with pytest.raises(GovernedShotKeyframeError, match="checksum"):
        store.require_approved(record.shot_id)


def test_manual_ltx25_workflow_is_governed_keyframe_i2v() -> None:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in workflow["nodes"]}

    assert nodes[2004]["widgets_values"][0] == "VSCS_SHT001_Governed_Keyframe.png"
    assert nodes[5508]["widgets_values"][0].startswith("Continue this exact shot.")
    assert "additional bridge crew" in nodes[5509]["widgets_values"][0]
    assert nodes[5511]["widgets_values"][0] == 24
    assert nodes[5512]["widgets_values"][0] == 6
    assert nodes[5014]["widgets_values"][0] is True
    assert nodes[5014]["widgets_values"][2] is False
    assert nodes[5514]["widgets_values"][-1] == 0.9
    assert nodes[5004]["widgets_values"] == [
        r"ltx2.5\ltx-2.5-audio-vae-bf16.safetensors",
        r"ltx2.5\ltx-2.5-video-vae-conv-bf16.safetensors",
        r"ltx2.5\ltx-2.5-22b-distilled-transformer-bf16.safetensors",
        r"ltx2.5\gemma4_e2b_it_bf16.safetensors",
        r"ltx2.5\gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
    ]

    contract = workflow["extra"]["vscs_phase_contract"]
    assert contract["candidate"] == "C"
    assert contract["architecture"] == "governed_keyframe_i2v"
    assert contract["combined_james_sandra_video_reference"] is False
