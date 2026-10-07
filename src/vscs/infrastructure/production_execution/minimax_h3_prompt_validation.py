"""MiniMax H3 provider prompt/metadata validation gates for Phase 20.18.2.3.6.4f.3."""

from __future__ import annotations

import re
from typing import ClassVar

from vscs.application.production_execution.provider_prompt_policy import (
    ProviderPromptPolicyResult,
)
from vscs.application.production_execution.provider_prompt_validation import (
    ProviderPromptValidationError,
    ProviderPromptValidationResult,
)
from vscs.application.production_execution.provider_span_governance import (
    ProviderSpanGovernance,
)
from vscs.application.production_execution.span_scoped_provider_inputs import (
    SpanReferenceSlot,
)


class MiniMaxH3PromptMetadataValidator:
    """Fail closed before an invalid H3 span can reach ComfyUI."""

    PROVIDER_ID = "minimax-h3-ref2va"
    VALIDATED_RULES = (
        "H3-001-future-assets-structurally-absent",
        "H3-002-span-local-timing-only",
        "H3-003-exact-character-authority",
        "H3-004-no-unapproved-people",
        "H3-005-frame-zero-guide-is-state-anchor",
        "H3-006-native-17k-plus-5-frame-grid",
        "H3-007-camera-instructions-consistent",
        "H3-008-introduction-continues-from-local-guide",
    )

    _SHOT_SIZE_PATTERNS: ClassVar[dict[str, re.Pattern[str]]] = {
        "wide": re.compile(r"\b(?:wide|wide shot|long shot|establishing shot)\b", re.IGNORECASE),
        "full": re.compile(r"\bfull shot\b", re.IGNORECASE),
        "medium": re.compile(r"\bmedium shot\b", re.IGNORECASE),
        "medium_close": re.compile(r"\bmedium[- ]close(?: shot)?\b", re.IGNORECASE),
        "close": re.compile(r"\bclose[- ]?up(?: shot)?\b", re.IGNORECASE),
        "extreme_close": re.compile(r"\bextreme close[- ]?up(?: shot)?\b", re.IGNORECASE),
    }

    def validate(
        self,
        *,
        governance: ProviderSpanGovernance,
        policy: ProviderPromptPolicyResult,
        reference_slots: tuple[SpanReferenceSlot, ...],
        provider_frame_count: int,
        guide_frame_idx: int,
        guide_semantics: str,
        temporal_asset_gate: bool,
    ) -> ProviderPromptValidationResult:
        self._require_source_identity(governance, policy)
        combined = " ".join((policy.positive_prompt, policy.negative_prompt, policy.motion_prompt))

        self._require_future_assets_absent(governance, reference_slots, combined)
        self._require_span_local_timing(governance, combined)
        self._require_exact_character_authority(governance, reference_slots, policy)
        self._require_no_unapproved_people(governance, policy)
        self._require_guide_semantics(
            guide_frame_idx=guide_frame_idx,
            guide_semantics=guide_semantics,
            temporal_asset_gate=temporal_asset_gate,
        )
        self._require_h3_frame_grid(governance, provider_frame_count)
        self._require_consistent_camera(policy)
        self._require_introduction_semantics(governance, reference_slots, policy)

        return ProviderPromptValidationResult(
            provider_id=self.PROVIDER_ID,
            span_id=governance.span_id,
            validated_rules=self.VALIDATED_RULES,
            source_policy_fingerprint=policy.fingerprint,
            source_governance_fingerprint=governance.fingerprint,
        )

    def _require_source_identity(
        self,
        governance: ProviderSpanGovernance,
        policy: ProviderPromptPolicyResult,
    ) -> None:
        if policy.provider_id != self.PROVIDER_ID:
            self._fail("H3-000", "prompt policy provider identity is not MiniMax H3")
        if policy.span_id != governance.span_id:
            self._fail("H3-000", "prompt policy span identity differs from governed metadata")
        if policy.source_governance_fingerprint != governance.fingerprint:
            self._fail("H3-000", "prompt policy source governance fingerprint is stale")

    def _require_future_assets_absent(
        self,
        governance: ProviderSpanGovernance,
        reference_slots: tuple[SpanReferenceSlot, ...],
        combined_prompt: str,
    ) -> None:
        slot_assets = {slot.asset_id for slot in reference_slots}
        future_assets = set(governance.future_asset_ids)
        leaked_slots = sorted(slot_assets & future_assets)
        if leaked_slots:
            self._fail(
                "H3-001",
                "future assets leaked into provider reference slots: " + ", ".join(leaked_slots),
            )
        inactive_slots = sorted(slot_assets - set(governance.active_asset_ids))
        if inactive_slots:
            self._fail(
                "H3-001",
                "inactive assets leaked into provider reference slots: "
                + ", ".join(inactive_slots),
            )
        lowered = combined_prompt.casefold()
        leaked_text = sorted(
            asset_id for asset_id in future_assets if asset_id.casefold() in lowered
        )
        if leaked_text:
            self._fail(
                "H3-001",
                "future asset identifiers leaked into provider prompts: " + ", ".join(leaked_text),
            )

    def _require_span_local_timing(
        self,
        governance: ProviderSpanGovernance,
        combined_prompt: str,
    ) -> None:
        if not governance.has_character_introduction:
            return
        timing_patterns = (
            re.compile(r"\bglobal\s+frames?\b", re.IGNORECASE),
            re.compile(r"\bframes?\s+\d+\s*(?:-|\\u2013|to|through)\s*\d+\b", re.IGNORECASE),
            re.compile(r"(?<![-\w])frame\s+\d+\b", re.IGNORECASE),
            re.compile(r"\b\d+(?:\.\d+)?\s*seconds?\b", re.IGNORECASE),
        )
        for pattern in timing_patterns:
            match = pattern.search(combined_prompt)
            if match is not None:
                self._fail(
                    "H3-002",
                    "introduction span contains non-local timing semantics: " + match.group(0),
                )

    def _require_exact_character_authority(
        self,
        governance: ProviderSpanGovernance,
        reference_slots: tuple[SpanReferenceSlot, ...],
        policy: ProviderPromptPolicyResult,
    ) -> None:
        active_characters = set(governance.active_character_asset_ids)
        character_slots = tuple(
            slot for slot in reference_slots if slot.asset_id in active_characters
        )
        if len(character_slots) != governance.exact_active_character_count:
            self._fail(
                "H3-003",
                "provider character reference count differs from governed exact count",
            )
        if {slot.asset_id for slot in character_slots} != active_characters:
            self._fail(
                "H3-003",
                "provider character references do not exactly match governed active characters",
            )
        if governance.has_character_introduction:
            expected = f"Exactly {governance.exact_active_character_count} people are visible"
            if expected.casefold() not in policy.positive_prompt.casefold():
                self._fail(
                    "H3-003",
                    "introduction prompt does not declare the governed exact visible-person count",
                )

    def _require_no_unapproved_people(
        self,
        governance: ProviderSpanGovernance,
        policy: ProviderPromptPolicyResult,
    ) -> None:
        if not governance.has_character_introduction:
            return
        positive = policy.positive_prompt.casefold()
        negative = policy.negative_prompt.casefold()
        motion = policy.motion_prompt.casefold()
        if "do not create any additional person" not in positive:
            self._fail("H3-004", "positive prompt does not prohibit additional people")
        if "no additional person enters or appears" not in motion:
            self._fail("H3-004", "motion prompt does not prohibit additional people")
        required_negative = ("extra people", "background people", "duplicated character")
        missing = tuple(item for item in required_negative if item not in negative)
        if missing:
            self._fail(
                "H3-004",
                "negative prompt is missing extra-person protections: " + ", ".join(missing),
            )

    def _require_guide_semantics(
        self,
        *,
        guide_frame_idx: int,
        guide_semantics: str,
        temporal_asset_gate: bool,
    ) -> None:
        if guide_frame_idx != 0:
            self._fail("H3-005", "isolated H3 guide must be bound to local frame 0")
        if guide_semantics != "frame_state_anchor":
            self._fail("H3-005", "H3 guide must be a frame-state anchor")
        if temporal_asset_gate is not False:
            self._fail("H3-005", "H3 guide must not be treated as a temporal asset gate")

    def _require_h3_frame_grid(
        self,
        governance: ProviderSpanGovernance,
        provider_frame_count: int,
    ) -> None:
        if provider_frame_count < governance.local_frame_count:
            self._fail("H3-006", "provider frame count is shorter than governed span")
        if provider_frame_count % 17 != 5:
            self._fail("H3-006", "provider frame count does not satisfy H3 17k+5 authority")

    def _require_consistent_camera(self, policy: ProviderPromptPolicyResult) -> None:
        text = " ".join((policy.positive_prompt, policy.motion_prompt))
        shot_sizes = {
            label
            for label, pattern in self._SHOT_SIZE_PATTERNS.items()
            if pattern.search(text) is not None
        }
        if len(shot_sizes) > 1:
            self._fail(
                "H3-007",
                "provider prompt contains conflicting shot-size instructions: "
                + ", ".join(sorted(shot_sizes)),
            )
        focal_lengths = set(re.findall(r"\b(\d{2,3})\s*mm\b", text, flags=re.IGNORECASE))
        if len(focal_lengths) > 1:
            self._fail(
                "H3-007",
                "provider prompt contains conflicting focal-length instructions",
            )

    def _require_introduction_semantics(
        self,
        governance: ProviderSpanGovernance,
        reference_slots: tuple[SpanReferenceSlot, ...],
        policy: ProviderPromptPolicyResult,
    ) -> None:
        if not governance.has_character_introduction:
            return
        by_asset = {slot.asset_id: slot for slot in reference_slots}
        introduced_tags: list[str] = []
        for asset_id in governance.introduced_character_asset_ids:
            slot = by_asset.get(asset_id)
            if slot is None:
                self._fail(
                    "H3-008",
                    f"introduced character {asset_id} has no provider reference slot",
                )
            introduced_tags.append(slot.picture_tag)

        positive = policy.positive_prompt.casefold()
        motion = policy.motion_prompt.casefold()
        if "already visible in the local frame-0 guide" not in positive:
            self._fail(
                "H3-008",
                "introduced character is not anchored as already visible at local frame 0",
            )
        if "continues natural movement from the guide position" not in motion:
            self._fail(
                "H3-008",
                "introduced character does not continue naturally from the guide position",
            )
        for tag in introduced_tags:
            if tag.casefold() not in positive or tag.casefold() not in motion:
                self._fail(
                    "H3-008",
                    f"introduced character reference {tag} is missing from local prompt semantics",
                )

    @staticmethod
    def _fail(rule_id: str, message: str) -> None:
        raise ProviderPromptValidationError(f"{rule_id}: {message}")
