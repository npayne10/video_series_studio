"""Provider prompt/metadata validation result contract for Phase 20.18.2.3.6.4f.3."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class ProviderPromptValidationError(ValueError):
    """Raised when provider prompt or metadata violates governed validation rules."""


@dataclass(frozen=True, slots=True)
class ProviderPromptValidationResult:
    """Deterministic evidence that one provider span passed pre-submission validation."""

    provider_id: str
    span_id: str
    validated_rules: tuple[str, ...]
    source_policy_fingerprint: str
    source_governance_fingerprint: str
    validation_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "provider_id",
            "span_id",
            "source_policy_fingerprint",
            "source_governance_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ProviderPromptValidationError(
                    f"Provider prompt validation requires {field_name}"
                )
            object.__setattr__(self, field_name, value)

        if self.validation_version != "1.0":
            raise ProviderPromptValidationError(
                "Provider prompt validation requires validation version 1.0"
            )

        rules = tuple(str(rule).strip() for rule in self.validated_rules)
        if not rules or any(not rule for rule in rules):
            raise ProviderPromptValidationError(
                "Provider prompt validation requires validated rules"
            )
        if len(set(rules)) != len(rules):
            raise ProviderPromptValidationError(
                "Provider prompt validation rules cannot contain duplicates"
            )
        object.__setattr__(self, "validated_rules", rules)
        object.__setattr__(
            self,
            "source_policy_fingerprint",
            self.source_policy_fingerprint.lower(),
        )
        object.__setattr__(
            self,
            "source_governance_fingerprint",
            self.source_governance_fingerprint.lower(),
        )

    @property
    def validation_id(self) -> str:
        return (
            f"PPV-{self.provider_id.upper()}-"
            f"{_fingerprint(self._authority_payload())[:12].upper()}"
        )

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def _authority_payload(self) -> dict[str, object]:
        return {
            "validation_version": self.validation_version,
            "provider_id": self.provider_id,
            "span_id": self.span_id,
            "validated_rules": list(self.validated_rules),
            "source_policy_fingerprint": self.source_policy_fingerprint,
            "source_governance_fingerprint": self.source_governance_fingerprint,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["validation_id"] = self.validation_id
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
