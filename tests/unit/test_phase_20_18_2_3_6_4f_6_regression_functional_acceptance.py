from __future__ import annotations

from vscs.infrastructure.production_execution import (
    MINIMAX_H3_EXECUTION_ADAPTER_ID,
    MINIMAX_H3_POLICY_PROFILE_ID,
    MiniMaxH3PromptMetadataValidator,
    default_provider_policy_profile_registry,
)


def test_h3_regression_catalog_is_complete_and_ordered() -> None:
    assert MiniMaxH3PromptMetadataValidator.VALIDATED_RULES == (
        "H3-001-future-assets-structurally-absent",
        "H3-002-span-local-timing-only",
        "H3-003-exact-character-authority",
        "H3-004-no-unapproved-people",
        "H3-005-frame-zero-guide-is-state-anchor",
        "H3-006-native-17k-plus-5-frame-grid",
        "H3-007-camera-instructions-consistent",
        "H3-008-introduction-continues-from-local-guide",
    )


def test_h3_functional_acceptance_profile_is_explicit_and_fingerprinted() -> None:
    profile = default_provider_policy_profile_registry().require(
        MINIMAX_H3_POLICY_PROFILE_ID
    )

    assert profile.provider_id == "minimax-h3-ref2va"
    assert profile.execution_adapter_id == MINIMAX_H3_EXECUTION_ADAPTER_ID
    assert profile.validation_policy_id == "h3-001-through-h3-008-v1"
    assert profile.guide_semantics == "frame_state_anchor"
    assert profile.temporal_asset_gate is False
    assert profile.native_frame_rule == "17k+5"
    assert len(profile.fingerprint) == 64


def test_h3_regression_profile_does_not_reintroduce_temporal_guide_gating() -> None:
    profile = default_provider_policy_profile_registry().require(
        MINIMAX_H3_POLICY_PROFILE_ID
    )

    assert profile.temporal_asset_gate is False
    assert profile.reference_projection_mode == "direct_span_scoped_canonical_refs"
    assert profile.max_reference_images == 5
