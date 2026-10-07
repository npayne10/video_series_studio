from __future__ import annotations

import pytest

from vscs.application.production_execution import (
    ProviderPromptPolicyError,
    ProviderSpanGovernance,
    SpanReferenceSlot,
)
from vscs.infrastructure.production_execution import MiniMaxH3PromptPolicyCompiler


def _governance(
    *,
    introduced: tuple[str, ...],
    active: tuple[str, ...],
    future: tuple[str, ...] = (),
) -> ProviderSpanGovernance:
    return ProviderSpanGovernance(
        span_id="IRS-SHT-002-002",
        sequence_number=2 if introduced else 1,
        global_start_frame=96 if introduced else 0,
        global_through_frame=143 if introduced else 95,
        local_start_frame=0,
        local_through_frame=47 if introduced else 95,
        local_frame_count=48 if introduced else 96,
        active_asset_ids=(*active, "CAP-LOC-021", "CAP-PLN-002"),
        active_character_asset_ids=active,
        introduced_asset_ids=introduced,
        introduced_character_asset_ids=introduced,
        future_asset_ids=future,
        future_character_asset_ids=future,
        exact_active_character_count=len(active),
        has_character_introduction=bool(introduced),
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


def test_initial_span_preserves_nonconflicting_span_scoped_prompts() -> None:
    governance = _governance(
        introduced=(),
        active=("CAP-CHR-001", "CAP-CHR-003"),
        future=("CAP-CHR-005",),
    )
    compiler = MiniMaxH3PromptPolicyCompiler()

    result = compiler.compile(
        governance=governance,
        reference_slots=(
            _slot(1, "CAP-CHR-001", "James"),
            _slot(2, "CAP-CHR-003", "Sandra"),
            _slot(3, "CAP-LOC-021", "Bridge"),
            _slot(4, "CAP-PLN-002", "Xorix"),
        ),
        base_positive_prompt="validated positive",
        base_negative_prompt="validated negative",
        base_motion_prompt="validated motion",
    )

    assert result.positive_prompt == "validated positive"
    assert result.negative_prompt == "validated negative"
    assert result.motion_prompt == "validated motion"
    assert "preserve_validated_span_scoped_prompt" in result.learned_rules
    assert "resolve_conflicting_camera_instructions" in result.learned_rules


def test_initial_span_resolves_conflicting_camera_instructions_deterministically() -> None:
    governance = _governance(
        introduced=(),
        active=("CAP-CHR-001", "CAP-CHR-003"),
        future=("CAP-CHR-005",),
    )

    result = MiniMaxH3PromptPolicyCompiler().compile(
        governance=governance,
        reference_slots=(
            _slot(1, "CAP-CHR-001", "James"),
            _slot(2, "CAP-CHR-003", "Sandra"),
            _slot(3, "CAP-LOC-021", "Bridge"),
            _slot(4, "CAP-PLN-002", "Xorix"),
        ),
        base_positive_prompt=(
            "Show the bridge with the two active characters. "
            "Hold one continuous wide, static, eye-level bridge shot. "
            "Preserve governed dialogue and identities. "
            "Use a medium close eye level 50 mm shot with a static camera, "
            "preserve eye-line and natural headroom."
        ),
        base_negative_prompt="no extras",
        base_motion_prompt=(
            "Hold one continuous wide, static, eye-level bridge shot. "
            "The camera remains locked in place throughout the shot."
        ),
    )

    combined = f"{result.positive_prompt} {result.motion_prompt}".casefold()
    assert "wide" in combined
    assert "medium close" not in combined
    assert "50 mm" not in combined
    assert "camera remains locked" in combined


def test_introduction_span_compiles_local_prompt_from_governed_metadata() -> None:
    governance = _governance(
        introduced=("CAP-CHR-005",),
        active=("CAP-CHR-001", "CAP-CHR-003", "CAP-CHR-005"),
    )
    compiler = MiniMaxH3PromptPolicyCompiler()
    stale_global_prompt = (
        "Frames 0-95 show James and Sandra. Ros is absent. "
        "At frame 96, 4.000 seconds, Ros enters. Medium close 50 mm."
    )

    result = compiler.compile(
        governance=governance,
        reference_slots=(
            _slot(1, "CAP-CHR-001", "James"),
            _slot(2, "CAP-CHR-003", "Sandra"),
            _slot(3, "CAP-CHR-005", "Ros"),
            _slot(4, "CAP-LOC-021", "Bridge"),
            _slot(5, "CAP-PLN-002", "Xorix"),
        ),
        base_positive_prompt=stale_global_prompt,
        base_negative_prompt="do not introduce Ros early",
        base_motion_prompt=stale_global_prompt,
    )

    combined = " ".join(
        (result.positive_prompt, result.negative_prompt, result.motion_prompt)
    ).casefold()

    assert "exactly 3 people" in combined
    assert "<picture 3>" in combined
    assert "local frame-0 guide" in combined
    assert "no additional person" in combined
    assert "frame 96" not in combined
    assert "4.000 seconds" not in combined
    assert "frames 0-95" not in combined
    assert "medium close" not in combined
    assert "50 mm" not in combined
    assert "do not introduce ros early" not in combined
    assert "span_local_timing_only" in result.learned_rules
    assert result.policy_id.startswith("PPP-MINIMAX-H3-REF2VA-")


def test_introduction_span_fails_closed_when_character_projection_is_incomplete() -> None:
    governance = _governance(
        introduced=("CAP-CHR-005",),
        active=("CAP-CHR-001", "CAP-CHR-003", "CAP-CHR-005"),
    )

    with pytest.raises(
        ProviderPromptPolicyError,
        match="active character count",
    ):
        MiniMaxH3PromptPolicyCompiler().compile(
            governance=governance,
            reference_slots=(
                _slot(1, "CAP-CHR-001", "James"),
                _slot(2, "CAP-CHR-003", "Sandra"),
                _slot(3, "CAP-LOC-021", "Bridge"),
                _slot(4, "CAP-PLN-002", "Xorix"),
            ),
            base_positive_prompt="positive",
            base_negative_prompt="negative",
            base_motion_prompt="motion",
        )
