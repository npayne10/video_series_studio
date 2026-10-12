"""Provider-aware direct-reference capacity projection."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from vscs.application.acpp.reference_roles import ReferencePriority, ReferenceRole
from vscs.application.production_execution.provider_policy_profiles import ProviderPolicyProfile


class ReferenceCapacityRecord(Protocol):
    """Minimum reviewed-reference facts required for direct-slot projection."""

    reference_id: str
    role: ReferenceRole
    priority: ReferencePriority
    provider_ready: bool


_NON_DIRECT_REFERENCE_ROLES = frozenset(
    {
        ReferenceRole.CONTINUITY_ANCHOR,
        ReferenceRole.START_FRAME_REFERENCE,
        ReferenceRole.END_FRAME_REFERENCE,
        ReferenceRole.MOTION_REFERENCE,
        ReferenceRole.STYLE_REFERENCE,
    }
)


@dataclass(frozen=True, slots=True)
class ProviderReferenceCapacityProjection:
    """Deterministic provider projection while preserving full governed authority."""

    provider_id: str
    provider_profile_id: str
    provider_profile_fingerprint: str
    model_family: str
    reference_projection_mode: str
    capacity: int
    required_reference_ids: tuple[str, ...]
    preferred_ready_reference_ids: tuple[str, ...]
    selected_reference_ids: tuple[str, ...]
    deferred_preferred_reference_ids: tuple[str, ...]
    indirect_projection: bool
    blocked_reason: str | None = None

    @property
    def passed(self) -> bool:
        return self.blocked_reason is None

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "provider_profile_id": self.provider_profile_id,
            "provider_profile_fingerprint": self.provider_profile_fingerprint,
            "model_family": self.model_family,
            "reference_projection_mode": self.reference_projection_mode,
            "capacity": self.capacity,
            "required_reference_ids": list(self.required_reference_ids),
            "preferred_ready_reference_ids": list(self.preferred_ready_reference_ids),
            "selected_reference_ids": list(self.selected_reference_ids),
            "deferred_preferred_reference_ids": list(self.deferred_preferred_reference_ids),
            "indirect_projection": self.indirect_projection,
            "passed": self.passed,
            "blocked_reason": self.blocked_reason,
        }


def project_provider_reference_capacity(
    profile: ProviderPolicyProfile,
    references: Iterable[ReferenceCapacityRecord],
) -> ProviderReferenceCapacityProjection:
    """Project reviewed references into provider direct slots deterministically.

    Full governed reference authority is preserved outside this projection. Required
    direct references are always selected first and are never silently dropped.
    Remaining direct slots are filled by provider-ready preferred references in
    governed review order. Optional references never consume scarce direct slots.
    Providers with a non-direct projection mode retain all governed authority but
    do not consume direct picture slots here.
    """

    values = tuple(references)
    direct = tuple(item for item in values if item.role not in _NON_DIRECT_REFERENCE_ROLES)
    required = tuple(
        item.reference_id for item in direct if item.priority is ReferencePriority.REQUIRED
    )
    preferred_ready = tuple(
        item.reference_id
        for item in direct
        if item.priority is ReferencePriority.PREFERRED and item.provider_ready
    )

    indirect = profile.reference_projection_mode != "direct_span_scoped_canonical_refs"
    if indirect:
        return ProviderReferenceCapacityProjection(
            provider_id=profile.provider_id,
            provider_profile_id=profile.profile_id,
            provider_profile_fingerprint=profile.fingerprint,
            model_family=profile.model_family,
            reference_projection_mode=profile.reference_projection_mode,
            capacity=profile.max_reference_images,
            required_reference_ids=required,
            preferred_ready_reference_ids=preferred_ready,
            selected_reference_ids=(),
            deferred_preferred_reference_ids=preferred_ready,
            indirect_projection=True,
        )

    capacity = profile.max_reference_images
    if capacity <= 0:
        return ProviderReferenceCapacityProjection(
            provider_id=profile.provider_id,
            provider_profile_id=profile.profile_id,
            provider_profile_fingerprint=profile.fingerprint,
            model_family=profile.model_family,
            reference_projection_mode=profile.reference_projection_mode,
            capacity=capacity,
            required_reference_ids=required,
            preferred_ready_reference_ids=preferred_ready,
            selected_reference_ids=(),
            deferred_preferred_reference_ids=preferred_ready,
            indirect_projection=False,
            blocked_reason=(
                f"{profile.model_family} declares direct-reference projection but no "
                "direct reference capacity"
            ),
        )

    if not required:
        return ProviderReferenceCapacityProjection(
            provider_id=profile.provider_id,
            provider_profile_id=profile.profile_id,
            provider_profile_fingerprint=profile.fingerprint,
            model_family=profile.model_family,
            reference_projection_mode=profile.reference_projection_mode,
            capacity=capacity,
            required_reference_ids=required,
            preferred_ready_reference_ids=preferred_ready,
            selected_reference_ids=(),
            deferred_preferred_reference_ids=preferred_ready,
            indirect_projection=False,
            blocked_reason="At least one required governed direct visual reference is required",
        )

    if len(required) > capacity:
        return ProviderReferenceCapacityProjection(
            provider_id=profile.provider_id,
            provider_profile_id=profile.profile_id,
            provider_profile_fingerprint=profile.fingerprint,
            model_family=profile.model_family,
            reference_projection_mode=profile.reference_projection_mode,
            capacity=capacity,
            required_reference_ids=required,
            preferred_ready_reference_ids=preferred_ready,
            selected_reference_ids=(),
            deferred_preferred_reference_ids=preferred_ready,
            indirect_projection=False,
            blocked_reason=(
                f"{len(required)} required governed direct references exceed provider "
                f"capacity {capacity}"
            ),
        )

    remaining = capacity - len(required)
    selected_preferred = preferred_ready[:remaining]
    deferred = preferred_ready[remaining:]
    selected = (*required, *selected_preferred)
    return ProviderReferenceCapacityProjection(
        provider_id=profile.provider_id,
        provider_profile_id=profile.profile_id,
        provider_profile_fingerprint=profile.fingerprint,
        model_family=profile.model_family,
        reference_projection_mode=profile.reference_projection_mode,
        capacity=capacity,
        required_reference_ids=required,
        preferred_ready_reference_ids=preferred_ready,
        selected_reference_ids=selected,
        deferred_preferred_reference_ids=deferred,
        indirect_projection=False,
    )
