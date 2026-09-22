"""Governed provider-audio policy for Phase 20.18.2.2h."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ProviderAudioPolicyError(RuntimeError):
    """Raised when provider-audio authority is invalid or unsupported."""


class ProviderAudioPolicyMode(StrEnum):
    """High-level provider-audio treatment selected by governed Shot authority."""

    SILENT_VISUAL = "silent_visual"
    GENERATED_AMBIENCE = "generated_ambience"
    CANONICAL_DIALOGUE = "canonical_dialogue"
    FIXED_AUDIO_CONDITIONING = "fixed_audio_conditioning"
    POST_DUB = "post_dub"


class ProviderAudioAction(StrEnum):
    """Concrete action VSCS takes before Generated Media ingestion."""

    DISCARD = "discard"
    PRESERVE_FOR_MIX = "preserve_for_mix"
    PRESERVE_FIXED = "preserve_fixed"


@dataclass(frozen=True, slots=True)
class ProviderAudioPolicy:
    """Resolved provider-audio authority for one compiled Shot."""

    mode: ProviderAudioPolicyMode
    provider_audio_action: ProviderAudioAction
    authoritative_audio_source: str
    rationale: str

    @property
    def discard_provider_audio(self) -> bool:
        return self.provider_audio_action is ProviderAudioAction.DISCARD

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_version": "1.0",
            "mode": self.mode.value,
            "provider_audio_action": self.provider_audio_action.value,
            "authoritative_audio_source": self.authoritative_audio_source,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ProviderAudioPolicy:
        if not isinstance(raw, dict):
            raise ProviderAudioPolicyError("Provider audio policy must be an object")
        if str(raw.get("schema_version", "")).strip() != "1.0":
            raise ProviderAudioPolicyError("Unsupported provider audio policy schema")
        try:
            mode = ProviderAudioPolicyMode(str(raw["mode"]).strip())
            action = ProviderAudioAction(str(raw["provider_audio_action"]).strip())
        except (KeyError, ValueError) as exc:
            raise ProviderAudioPolicyError("Provider audio policy mode/action is invalid") from exc
        source = str(raw.get("authoritative_audio_source", "")).strip()
        rationale = str(raw.get("rationale", "")).strip()
        if not source:
            raise ProviderAudioPolicyError(
                "Provider audio policy requires authoritative_audio_source"
            )
        if not rationale:
            raise ProviderAudioPolicyError("Provider audio policy requires rationale")
        expected = _policy_for_mode(mode)
        if action is not expected.provider_audio_action:
            raise ProviderAudioPolicyError(
                f"Provider audio action {action.value!r} is incompatible with mode {mode.value!r}"
            )
        if source != expected.authoritative_audio_source:
            raise ProviderAudioPolicyError(
                "Provider audio authoritative source is incompatible with the selected mode"
            )
        return cls(mode, action, source, rationale)


def resolve_provider_audio_policy(production_authority: dict[str, Any]) -> ProviderAudioPolicy:
    """Resolve a deterministic policy from explicit authority or governed dialogue state."""
    explicit = production_authority.get("provider_audio_policy")
    if explicit is not None:
        mode = _explicit_mode(explicit)
        return _policy_for_mode(mode)

    if _has_governed_dialogue(production_authority):
        return _policy_for_mode(ProviderAudioPolicyMode.CANONICAL_DIALOGUE)
    return _policy_for_mode(ProviderAudioPolicyMode.SILENT_VISUAL)


def _explicit_mode(raw: object) -> ProviderAudioPolicyMode:
    if isinstance(raw, str):
        value = raw.strip()
    elif isinstance(raw, dict):
        value = str(raw.get("mode", "")).strip()
    else:
        raise ProviderAudioPolicyError("Explicit provider_audio_policy must be a string or object")
    try:
        return ProviderAudioPolicyMode(value)
    except ValueError as exc:
        raise ProviderAudioPolicyError(
            f"Unsupported provider audio policy mode: {value!r}"
        ) from exc


def _policy_for_mode(mode: ProviderAudioPolicyMode) -> ProviderAudioPolicy:
    if mode is ProviderAudioPolicyMode.SILENT_VISUAL:
        return ProviderAudioPolicy(
            mode,
            ProviderAudioAction.DISCARD,
            "vscs_audio_pipeline",
            "Shot is visually generated without authoritative provider audio.",
        )
    if mode is ProviderAudioPolicyMode.CANONICAL_DIALOGUE:
        return ProviderAudioPolicy(
            mode,
            ProviderAudioAction.DISCARD,
            "vscs_audio_pipeline",
            "Dialogue authority belongs to the VSCS voice/audio pipeline, not the video provider.",
        )
    if mode is ProviderAudioPolicyMode.POST_DUB:
        return ProviderAudioPolicy(
            mode,
            ProviderAudioAction.DISCARD,
            "vscs_audio_pipeline",
            "Provider speech is discarded because dialogue will be applied in post-dub.",
        )
    if mode is ProviderAudioPolicyMode.GENERATED_AMBIENCE:
        return ProviderAudioPolicy(
            mode,
            ProviderAudioAction.PRESERVE_FOR_MIX,
            "vscs_audio_pipeline",
            "Provider ambience may be retained as a non-final source for the VSCS mix.",
        )
    return ProviderAudioPolicy(
        mode,
        ProviderAudioAction.PRESERVE_FIXED,
        "fixed_audio_conditioning",
        "Supplied fixed audio is authoritative conditioning and must remain unchanged.",
    )


def _has_governed_dialogue(production_authority: dict[str, Any]) -> bool:
    action = production_authority.get("action_performance")
    if isinstance(action, dict) and str(action.get("spoken_content", "")).strip():
        return True
    dialogue = production_authority.get("dialogue")
    if not isinstance(dialogue, list):
        return False
    for item in dialogue:
        if not isinstance(item, dict):
            continue
        for key in ("text", "line", "spoken_content", "dialogue"):
            if str(item.get(key, "")).strip():
                return True
    return False
