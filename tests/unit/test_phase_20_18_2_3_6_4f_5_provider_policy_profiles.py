from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.production_execution import (
    ProviderPolicyProfileError,
)
from vscs.infrastructure.production_execution import (
    LTX25SpanConditioningError,
    LTX25SpanProviderConditioningCompiler,
    MiniMaxH3AutomatedExecutionError,
    MiniMaxH3AutomatedExecutionService,
    default_provider_policy_profile_registry,
)


def _runtime_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    input_dir = tmp_path / "ComfyUI" / "input"
    output_dir = tmp_path / "ComfyUI" / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    workflow = tmp_path / "workflow.json"
    workflow.write_text("{}", encoding="utf-8")
    return input_dir, output_dir, workflow


def test_default_provider_policy_profiles_are_explicit_and_distinct() -> None:
    registry = default_provider_policy_profile_registry()

    h3 = registry.require("minimax-h3-ref2va-v1")
    ltx = registry.require("ltx-2.5-candidate-c-v1")

    assert h3.provider_id == "minimax-h3-ref2va"
    assert h3.prompt_policy_id == "learned_span_local_v1"
    assert h3.validation_policy_id == "h3-001-through-h3-008-v1"
    assert h3.reference_projection_mode == "direct_span_scoped_canonical_refs"
    assert h3.guide_semantics == "frame_state_anchor"
    assert h3.native_frame_rule == "17k+5"
    assert h3.max_reference_images == 5
    assert h3.temporal_asset_gate is False

    assert ltx.provider_id == "ltx-2.5"
    assert ltx.prompt_policy_id == "motion_only_v2"
    assert ltx.validation_policy_id == "governed_keyframe_candidate_c_v1"
    assert ltx.reference_projection_mode == "baked_into_governed_keyframe"
    assert ltx.guide_semantics == "first_frame_i2v"
    assert ltx.native_frame_rule == "8k+1"
    assert ltx.max_reference_images == 0
    assert ltx.temporal_asset_gate is False

    assert h3.fingerprint != ltx.fingerprint
    assert len(h3.fingerprint) == 64
    assert len(ltx.fingerprint) == 64


def test_provider_policy_registry_fails_closed_for_unknown_profile() -> None:
    registry = default_provider_policy_profile_registry()

    with pytest.raises(ProviderPolicyProfileError, match="Unknown provider policy profile"):
        registry.require("wan-future-profile")


def test_h3_automated_execution_rejects_ltx_policy_profile(tmp_path: Path) -> None:
    registry = default_provider_policy_profile_registry()
    ltx = registry.require("ltx-2.5-candidate-c-v1")
    input_dir, output_dir, workflow = _runtime_paths(tmp_path)

    with pytest.raises(
        MiniMaxH3AutomatedExecutionError,
        match="incompatible with H3 automated execution",
    ):
        MiniMaxH3AutomatedExecutionService(
            tmp_path,
            endpoint="http://127.0.0.1:8188",
            comfyui_input_directory=input_dir,
            comfyui_output_directory=output_dir,
            workflow_path=workflow,
            policy_profile=ltx,
        )


def test_ltx25_conditioning_rejects_h3_policy_profile(tmp_path: Path) -> None:
    registry = default_provider_policy_profile_registry()
    h3 = registry.require("minimax-h3-ref2va-v1")

    with pytest.raises(
        LTX25SpanConditioningError,
        match="incompatible with LTX-2.5 conditioning",
    ):
        LTX25SpanProviderConditioningCompiler(
            tmp_path,
            policy_profile=h3,
        )


def test_provider_lookup_exposes_each_installed_policy_profile() -> None:
    registry = default_provider_policy_profile_registry()

    h3 = registry.for_provider("minimax-h3-ref2va")
    ltx = registry.for_provider("ltx-2.5")

    assert tuple(profile.profile_id for profile in h3) == ("minimax-h3-ref2va-v1",)
    assert tuple(profile.profile_id for profile in ltx) == ("ltx-2.5-candidate-c-v1",)
