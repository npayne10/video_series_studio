"""Installed provider policy profiles for governed local video generation."""

from __future__ import annotations

from vscs.application.production_execution.provider_policy_profiles import (
    ProviderPolicyProfile,
    ProviderPolicyProfileRegistry,
)

MINIMAX_H3_POLICY_PROFILE_ID = "minimax-h3-ref2va-v1"
LTX25_CANDIDATE_C_POLICY_PROFILE_ID = "ltx-2.5-candidate-c-v1"

MINIMAX_H3_EXECUTION_ADAPTER_ID = "minimax_h3_automated_execution"
LTX25_EXECUTION_ADAPTER_ID = "ltx25_automated_span_orchestration"


def default_provider_policy_profile_registry() -> ProviderPolicyProfileRegistry:
    """Return the installed, explicit provider-policy choices for local execution."""
    return ProviderPolicyProfileRegistry(
        (
            ProviderPolicyProfile(
                profile_id=MINIMAX_H3_POLICY_PROFILE_ID,
                provider_id="minimax-h3-ref2va",
                model_family="MiniMax H3",
                prompt_policy_id="learned_span_local_v1",
                validation_policy_id="h3-001-through-h3-008-v1",
                reference_projection_mode="direct_span_scoped_canonical_refs",
                guide_semantics="frame_state_anchor",
                temporal_asset_gate=False,
                native_frame_rule="17k+5",
                max_reference_images=5,
                execution_adapter_id=MINIMAX_H3_EXECUTION_ADAPTER_ID,
            ),
            ProviderPolicyProfile(
                profile_id=LTX25_CANDIDATE_C_POLICY_PROFILE_ID,
                provider_id="ltx-2.5",
                model_family="LTX-2.5",
                prompt_policy_id="motion_only_v2",
                validation_policy_id="governed_keyframe_candidate_c_v1",
                reference_projection_mode="baked_into_governed_keyframe",
                guide_semantics="first_frame_i2v",
                temporal_asset_gate=False,
                native_frame_rule="8k+1",
                max_reference_images=0,
                execution_adapter_id=LTX25_EXECUTION_ADAPTER_ID,
            ),
        )
    )
