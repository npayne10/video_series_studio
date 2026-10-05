"""Provider prompt-policy result contract for automated provider prompt governance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class ProviderPromptPolicyError(ValueError):
    """Raised when learned provider prompt policy cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class ProviderPromptPolicyResult:
    """Deterministic provider prompt set produced from governed span metadata."""

    provider_id: str
    span_id: str
    positive_prompt: str
    negative_prompt: str
    motion_prompt: str
    learned_rules: tuple[str, ...]
    source_governance_fingerprint: str
    policy_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "provider_id",
            "span_id",
            "positive_prompt",
            "negative_prompt",
            "motion_prompt",
            "source_governance_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ProviderPromptPolicyError(
                    f"Provider prompt policy result requires {field_name}"
                )
            object.__setattr__(self, field_name, value)

        if self.policy_version != "1.0":
            raise ProviderPromptPolicyError(
                "Provider prompt policy result requires policy version 1.0"
            )

        rules = tuple(str(rule).strip() for rule in self.learned_rules)
        if not rules or any(not rule for rule in rules):
            raise ProviderPromptPolicyError(
                "Provider prompt policy result requires learned rules"
            )
        if len(set(rules)) != len(rules):
            raise ProviderPromptPolicyError(
                "Provider prompt policy learned rules cannot contain duplicates"
            )
        object.__setattr__(self, "learned_rules", rules)
        object.__setattr__(
            self,
            "source_governance_fingerprint",
            self.source_governance_fingerprint.lower(),
        )

    @property
    def policy_id(self) -> str:
        return (
            f"PPP-{self.provider_id.upper()}-"
            f"{_fingerprint(self._authority_payload())[:12].upper()}"
        )

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def _authority_payload(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "provider_id": self.provider_id,
            "span_id": self.span_id,
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "motion_prompt": self.motion_prompt,
            "learned_rules": list(self.learned_rules),
            "source_governance_fingerprint": self.source_governance_fingerprint,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["policy_id"] = self.policy_id
        payload["fingerprint"] = self.fingerprint
        return payload


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
