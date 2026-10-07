"""Learned MiniMax H3 prompt policy for Phase 20.18.2.3.6.4f.2."""

from __future__ import annotations

import re
from vscs.application.production_execution.provider_prompt_policy import (
    ProviderPromptPolicyError,
    ProviderPromptPolicyResult,
)
from vscs.application.production_execution.provider_span_governance import (
    ProviderSpanGovernance,
)
from vscs.application.production_execution.span_scoped_provider_inputs import (
    SpanReferenceSlot,
)


class MiniMaxH3PromptPolicyCompiler:
    """Translate governed span metadata into deterministic H3-local prompts."""

    PROVIDER_ID = "minimax-h3-ref2va"

    INITIAL_RULES = (
        "preserve_validated_span_scoped_prompt",
        "resolve_conflicting_camera_instructions",
        "future_assets_structurally_absent",
        "frame_zero_guide_is_state_anchor_not_temporal_gate",
    )
    INTRODUCTION_RULES = (
        "span_local_timing_only",
        "frame_zero_guide_is_state_anchor_not_temporal_gate",
        "exact_active_character_count",
        "no_unapproved_people",
        "introduced_character_continues_from_frame_zero",
        "preserve_established_composition",
        "future_assets_structurally_absent",
    )

    def compile(
        self,
        *,
        governance: ProviderSpanGovernance,
        reference_slots: tuple[SpanReferenceSlot, ...],
        base_positive_prompt: str,
        base_negative_prompt: str,
        base_motion_prompt: str,
    ) -> ProviderPromptPolicyResult:
        if not governance.has_character_introduction:
            positive_prompt, camera_authority = self._resolve_camera_instructions(
                base_positive_prompt
            )
            motion_prompt, _ = self._resolve_camera_instructions(
                base_motion_prompt,
                camera_authority=camera_authority,
            )
            return ProviderPromptPolicyResult(
                provider_id=self.PROVIDER_ID,
                span_id=governance.span_id,
                positive_prompt=positive_prompt,
                negative_prompt=base_negative_prompt,
                motion_prompt=motion_prompt,
                learned_rules=self.INITIAL_RULES,
                source_governance_fingerprint=governance.fingerprint,
            )

        active_characters = set(governance.active_character_asset_ids)
        introduced_characters = set(governance.introduced_character_asset_ids)

        character_slots = tuple(
            slot for slot in reference_slots if slot.asset_id in active_characters
        )
        introduced_slots = tuple(
            slot for slot in character_slots if slot.asset_id in introduced_characters
        )

        if len(character_slots) != governance.exact_active_character_count:
            raise ProviderPromptPolicyError(
                "H3 prompt policy character slots do not match governed active character count"
            )
        if {slot.asset_id for slot in character_slots} != active_characters:
            raise ProviderPromptPolicyError(
                "H3 prompt policy is missing governed active character references"
            )
        if {slot.asset_id for slot in introduced_slots} != introduced_characters:
            raise ProviderPromptPolicyError(
                "H3 prompt policy is missing governed introduced character references"
            )

        declaration = " ".join(
            f"{slot.picture_tag} is the authoritative reference for {slot.semantic_label}."
            for slot in reference_slots
        )
        character_tags = ", ".join(slot.picture_tag for slot in character_slots)
        introduced_tags = ", ".join(slot.picture_tag for slot in introduced_slots)

        positive = " ".join(
            (
                declaration,
                "Use the local frame-0 guide as the authoritative starting composition.",
                "Preserve the established composition, camera, lighting, environment, "
                "spatial relationships, and character identities shown by the guide.",
                f"Exactly {governance.exact_active_character_count} people are visible, "
                f"corresponding only to these active character references: {character_tags}.",
                "Do not create any additional person or crew member.",
                f"The character introduced at this span opening ({introduced_tags}) is already "
                "visible in the local frame-0 guide and continues natural motion from that "
                "guide position.",
                "All other established characters remain continuous with only natural motion.",
                "Preserve governed empty positions, unoccupied furniture, and clear spaces "
                "shown by the frame-0 guide.",
            )
        )

        negative = "; ".join(
            (
                "extra people",
                "additional crew",
                "unidentified people",
                "background people",
                "duplicate human figure",
                "duplicated character",
                "identity swap",
                "merged identity",
                "character replacement",
                "reflections resembling people",
                "new human figure",
                "camera cut",
                "scene cut",
                "split screen",
                "contact sheet",
                "tiled references",
                "generated speech",
                "invented dialogue",
                "unscripted voice",
            )
        )

        motion = " ".join(
            (
                "Keep the camera locked to the local frame-0 guide composition.",
                f"The introduced character ({introduced_tags}) continues natural movement "
                "from the guide position.",
                "The other established characters use only subtle natural movement.",
                "No additional person enters or appears.",
                "Preserve environmental continuity and the spatial state established by the guide.",
            )
        )

        return ProviderPromptPolicyResult(
            provider_id=self.PROVIDER_ID,
            span_id=governance.span_id,
            positive_prompt=positive,
            negative_prompt=negative,
            motion_prompt=motion,
            learned_rules=self.INTRODUCTION_RULES,
            source_governance_fingerprint=governance.fingerprint,
        )

    _SHOT_SIZE_PATTERNS = (
        ("wide", re.compile(r"\\b(?:wide|wide shot|long shot|establishing shot)\\b", re.IGNORECASE)),
        ("full", re.compile(r"\\bfull shot\\b", re.IGNORECASE)),
        ("medium", re.compile(r"\\bmedium shot\\b", re.IGNORECASE)),
        (
            "medium_close",
            re.compile(r"\\bmedium[- ]close(?: shot)?\\b", re.IGNORECASE),
        ),
        ("close", re.compile(r"\\bclose[- ]?up(?: shot)?\\b", re.IGNORECASE)),
        (
            "extreme_close",
            re.compile(r"\\bextreme close[- ]?up(?: shot)?\\b", re.IGNORECASE),
        ),
    )
    _FOCAL_LENGTH_PATTERN = re.compile(r"\\b(\\d{2,3})\\s*mm\\b", re.IGNORECASE)
    _SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\\s+")

    def _resolve_camera_instructions(
        self,
        prompt: str,
        *,
        camera_authority: tuple[frozenset[str], frozenset[str]] | None = None,
    ) -> tuple[str, tuple[frozenset[str], frozenset[str]]]:
        """Keep the first coherent camera instruction and drop later conflicts."""
        shot_sizes = set(camera_authority[0]) if camera_authority is not None else set()
        focal_lengths = set(camera_authority[1]) if camera_authority is not None else set()
        kept: list[str] = []

        for sentence in self._SENTENCE_BOUNDARY_PATTERN.split(prompt.strip()):
            normalized = sentence.strip()
            if not normalized:
                continue

            sentence_sizes = {
                label
                for label, pattern in self._SHOT_SIZE_PATTERNS
                if pattern.search(normalized) is not None
            }
            sentence_focals = set(self._FOCAL_LENGTH_PATTERN.findall(normalized))

            if len(sentence_sizes) > 1:
                raise ProviderPromptPolicyError(
                    "H3 prompt policy received one camera instruction with conflicting shot sizes"
                )
            if len(sentence_focals) > 1:
                raise ProviderPromptPolicyError(
                    "H3 prompt policy received one camera instruction with conflicting focal lengths"
                )

            if shot_sizes and sentence_sizes and sentence_sizes != shot_sizes:
                continue
            if focal_lengths and sentence_focals and sentence_focals != focal_lengths:
                continue

            if not shot_sizes and sentence_sizes:
                shot_sizes.update(sentence_sizes)
            if not focal_lengths and sentence_focals:
                focal_lengths.update(sentence_focals)
            kept.append(normalized)

        resolved = " ".join(kept).strip()
        if not resolved:
            raise ProviderPromptPolicyError(
                "H3 prompt policy removed every initial-span prompt instruction"
            )
        return resolved, (frozenset(shot_sizes), frozenset(focal_lengths))
