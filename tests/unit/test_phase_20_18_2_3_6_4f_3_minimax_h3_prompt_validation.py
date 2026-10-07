from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.production_execution import (
    ProviderPromptPolicyResult,
    ProviderPromptValidationError,
    ProviderSpanGovernance,
    SpanReferenceSlot,
)
from vscs.infrastructure.production_execution import (
    MiniMaxH3PromptMetadataValidator,
    MiniMaxH3PromptPolicyCompiler,
)


def _governance() -> ProviderSpanGovernance:
    return ProviderSpanGovernance(
        span_id="IRS-SHT-002-002",
        sequence_number=2,
        global_start_frame=96,
        global_through_frame=143,
        local_start_frame=0,
        local_through_frame=47,
        local_frame_count=48,
        active_asset_ids=(
            "CAP-CHR-001",
            "CAP-CHR-003",
            "CAP-CHR-005",
            "CAP-LOC-021",
            "CAP-PLN-002",
        ),
        active_character_asset_ids=("CAP-CHR-001", "CAP-CHR-003", "CAP-CHR-005"),
        introduced_asset_ids=("CAP-CHR-005",),
        introduced_character_asset_ids=("CAP-CHR-005",),
        future_asset_ids=(),
        future_character_asset_ids=(),
        exact_active_character_count=3,
        has_character_introduction=True,
        source_execution_id="PTSE-SHT-002-002",
        source_execution_plan_fingerprint="a" * 64,
    )


def _slot(index: int, asset_id: str, label: str) -> SpanReferenceSlot:
    return SpanReferenceSlot(
        picture_index=index,
        picture_tag=f"<Picture {index}>",
        reference_id=f"REF-{asset_id}",
        asset_id=asset_id,
        role="identity" if "CHR" in asset_id else "environment_reference",
        source_path=f"references/{asset_id}.png",
        semantic_label=label,
    )


def _slots() -> tuple[SpanReferenceSlot, ...]:
    return (
        _slot(1, "CAP-CHR-001", "James"),
        _slot(2, "CAP-CHR-003", "Sandra"),
        _slot(3, "CAP-CHR-005", "Ros"),
        _slot(4, "CAP-LOC-021", "Bridge"),
        _slot(5, "CAP-PLN-002", "Xorix"),
    )


def _policy(
    governance: ProviderSpanGovernance | None = None,
) -> ProviderPromptPolicyResult:
    governed = governance or _governance()
    return MiniMaxH3PromptPolicyCompiler().compile(
        governance=governed,
        reference_slots=_slots(),
        base_positive_prompt="unused stale global prompt",
        base_negative_prompt="unused stale negative prompt",
        base_motion_prompt="unused stale motion prompt",
    )


def _validate(
    *,
    governance: ProviderSpanGovernance | None = None,
    policy: ProviderPromptPolicyResult | None = None,
    slots: tuple[SpanReferenceSlot, ...] | None = None,
    provider_frame_count: int = 56,
    guide_frame_idx: int = 0,
    guide_semantics: str = "frame_state_anchor",
    temporal_asset_gate: bool = False,
):
    governed = governance or _governance()
    return MiniMaxH3PromptMetadataValidator().validate(
        governance=governed,
        policy=policy or _policy(governed),
        reference_slots=slots or _slots(),
        provider_frame_count=provider_frame_count,
        guide_frame_idx=guide_frame_idx,
        guide_semantics=guide_semantics,
        temporal_asset_gate=temporal_asset_gate,
    )


def test_h3_validation_accepts_learned_introduction_policy() -> None:
    result = _validate()

    assert result.provider_id == "minimax-h3-ref2va"
    assert result.span_id == "IRS-SHT-002-002"
    assert len(result.validated_rules) == 8
    assert result.validation_id.startswith("PPV-MINIMAX-H3-REF2VA-")


def test_h3_validation_rejects_stale_global_timing() -> None:
    governed = _governance()
    valid = _policy(governed)
    bad = replace(
        valid,
        positive_prompt=valid.positive_prompt + " Ros enters at frame 96 after 4.000 seconds.",
    )

    with pytest.raises(ProviderPromptValidationError, match="H3-002"):
        _validate(governance=governed, policy=bad)


def test_h3_validation_rejects_future_reference_slot_leak() -> None:
    governed = replace(
        _governance(),
        future_asset_ids=("CAP-CHR-009",),
        future_character_asset_ids=("CAP-CHR-009",),
    )
    leaked = (*_slots(), _slot(6, "CAP-CHR-009", "Future Character"))

    with pytest.raises(ProviderPromptValidationError, match="H3-001"):
        _validate(governance=governed, policy=_policy(governed), slots=leaked)


def test_h3_validation_rejects_character_reference_mismatch() -> None:
    incomplete = tuple(slot for slot in _slots() if slot.asset_id != "CAP-CHR-003")

    with pytest.raises(ProviderPromptValidationError, match="H3-003"):
        _validate(slots=incomplete)


def test_h3_validation_rejects_wrong_guide_semantics() -> None:
    with pytest.raises(ProviderPromptValidationError, match="H3-005"):
        _validate(temporal_asset_gate=True)


def test_h3_validation_rejects_non_native_frame_grid() -> None:
    with pytest.raises(ProviderPromptValidationError, match="H3-006"):
        _validate(provider_frame_count=55)


def test_h3_validation_rejects_conflicting_camera_instructions() -> None:
    governed = _governance()
    valid = _policy(governed)
    bad = replace(
        valid,
        positive_prompt=valid.positive_prompt + " Use a wide shot and a medium close shot.",
    )

    with pytest.raises(ProviderPromptValidationError, match="H3-007"):
        _validate(governance=governed, policy=bad)


def test_h3_validation_rejects_locked_camera_with_movement_instruction() -> None:
    governed = _governance()
    valid = _policy(governed)
    bad = replace(
        valid,
        motion_prompt=(
            valid.motion_prompt
            + " The camera remains locked in place throughout the shot. Camera pans right."
        ),
    )

    with pytest.raises(ProviderPromptValidationError, match="H3-007"):
        _validate(governance=governed, policy=bad)


def test_h3_validation_accepts_initial_span_after_camera_policy_resolution() -> None:
    governed = ProviderSpanGovernance(
        span_id="IRS-SHT-002-001",
        sequence_number=1,
        global_start_frame=0,
        global_through_frame=95,
        local_start_frame=0,
        local_through_frame=95,
        local_frame_count=96,
        active_asset_ids=("CAP-CHR-001", "CAP-CHR-003", "CAP-LOC-021", "CAP-PLN-002"),
        active_character_asset_ids=("CAP-CHR-001", "CAP-CHR-003"),
        introduced_asset_ids=(),
        introduced_character_asset_ids=(),
        future_asset_ids=("CAP-CHR-005",),
        future_character_asset_ids=("CAP-CHR-005",),
        exact_active_character_count=2,
        has_character_introduction=False,
        source_execution_id="PTSE-SHT-002-001",
        source_execution_plan_fingerprint="b" * 64,
    )
    slots = (
        _slot(1, "CAP-CHR-001", "James"),
        _slot(2, "CAP-CHR-003", "Sandra"),
        _slot(3, "CAP-LOC-021", "Bridge"),
        _slot(4, "CAP-PLN-002", "Xorix"),
    )
    policy = MiniMaxH3PromptPolicyCompiler().compile(
        governance=governed,
        reference_slots=slots,
        base_positive_prompt=(
            "Hold one continuous wide, static, eye-level bridge shot. "
            "Use a medium close eye level 50 mm shot with a static camera."
        ),
        base_negative_prompt="no extras",
        base_motion_prompt="Hold one continuous wide, static, eye-level bridge shot.",
    )

    result = MiniMaxH3PromptMetadataValidator().validate(
        governance=governed,
        policy=policy,
        reference_slots=slots,
        provider_frame_count=107,
        guide_frame_idx=0,
        guide_semantics="frame_state_anchor",
        temporal_asset_gate=False,
    )

    assert result.span_id == governed.span_id
    assert "medium close" not in policy.positive_prompt.casefold()
    assert "50 mm" not in policy.positive_prompt.casefold()


def test_h3_validation_rejects_invalid_introduction_semantics() -> None:
    governed = _governance()
    valid = _policy(governed)
    bad = replace(
        valid,
        motion_prompt="Keep camera locked. No additional person enters or appears.",
    )

    with pytest.raises(ProviderPromptValidationError, match="H3-008"):
        _validate(governance=governed, policy=bad)
