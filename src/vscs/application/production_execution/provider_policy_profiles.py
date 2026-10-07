"""Provider-neutral policy-profile contracts for governed video execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class ProviderPolicyProfileError(ValueError):
    """Raised when provider policy-profile authority is invalid or ambiguous."""


@dataclass(frozen=True, slots=True)
class ProviderPolicyProfile:
    """Deterministic provider-specific policy selected below governed Shot authority."""

    profile_id: str
    provider_id: str
    model_family: str
    prompt_policy_id: str
    validation_policy_id: str
    reference_projection_mode: str
    guide_semantics: str
    temporal_asset_gate: bool
    native_frame_rule: str
    max_reference_images: int
    execution_adapter_id: str
    enabled: bool = True
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "profile_id",
            "provider_id",
            "model_family",
            "prompt_policy_id",
            "validation_policy_id",
            "reference_projection_mode",
            "guide_semantics",
            "native_frame_rule",
            "execution_adapter_id",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ProviderPolicyProfileError(f"Provider policy profile requires {field_name}")
            object.__setattr__(self, field_name, value)
        if self.schema_version != "1.0":
            raise ProviderPolicyProfileError("Provider policy profile requires schema version 1.0")
        if self.max_reference_images < 0:
            raise ProviderPolicyProfileError(
                "Provider policy profile max_reference_images cannot be negative"
            )

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "provider_id": self.provider_id,
            "model_family": self.model_family,
            "prompt_policy_id": self.prompt_policy_id,
            "validation_policy_id": self.validation_policy_id,
            "reference_projection_mode": self.reference_projection_mode,
            "guide_semantics": self.guide_semantics,
            "temporal_asset_gate": self.temporal_asset_gate,
            "native_frame_rule": self.native_frame_rule,
            "max_reference_images": self.max_reference_images,
            "execution_adapter_id": self.execution_adapter_id,
            "enabled": self.enabled,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["fingerprint"] = self.fingerprint
        return payload


class ProviderPolicyProfileRegistry:
    """Resolve one explicit provider policy profile without changing upstream authority."""

    def __init__(self, profiles: tuple[ProviderPolicyProfile, ...]) -> None:
        if not profiles:
            raise ProviderPolicyProfileError(
                "Provider policy profile registry requires at least one profile"
            )
        by_id: dict[str, ProviderPolicyProfile] = {}
        for profile in profiles:
            key = profile.profile_id.casefold()
            if key in by_id:
                raise ProviderPolicyProfileError(
                    f"Duplicate provider policy profile: {profile.profile_id}"
                )
            by_id[key] = profile
        self._profiles = tuple(profiles)
        self._by_id = by_id

    @property
    def profiles(self) -> tuple[ProviderPolicyProfile, ...]:
        return self._profiles

    @property
    def enabled_profiles(self) -> tuple[ProviderPolicyProfile, ...]:
        return tuple(profile for profile in self._profiles if profile.enabled)

    def require(self, profile_id: str) -> ProviderPolicyProfile:
        normalized = profile_id.strip().casefold()
        if not normalized:
            raise ProviderPolicyProfileError("Provider policy profile selection cannot be blank")
        profile = self._by_id.get(normalized)
        if profile is None:
            supported = ", ".join(profile.profile_id for profile in self._profiles)
            raise ProviderPolicyProfileError(
                f"Unknown provider policy profile {profile_id!r}; expected one of {supported}"
            )
        if not profile.enabled:
            raise ProviderPolicyProfileError(
                f"Provider policy profile is disabled: {profile.profile_id}"
            )
        return profile

    def for_provider(self, provider_id: str) -> tuple[ProviderPolicyProfile, ...]:
        normalized = provider_id.strip().casefold()
        return tuple(
            profile
            for profile in self.enabled_profiles
            if profile.provider_id.casefold() == normalized
        )


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
