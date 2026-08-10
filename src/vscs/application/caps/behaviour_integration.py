"""Governed CAP to Behaviour Profile integration for Phase 19.2.5."""

from __future__ import annotations

from vscs.application.behaviours import BehaviourProfileService
from vscs.application.caps.service import CAPService
from vscs.domain.behaviours import BehaviourProfile
from vscs.domain.caps import CanonicalAssetProfile, CAPUpdate


class CAPBehaviourIntegrationError(RuntimeError):
    """Raised when CAP to Behaviour Profile linkage is invalid."""


class BehaviourProfileUnavailableError(CAPBehaviourIntegrationError):
    """Raised when a CAP references a BEP without production authority."""


class BehaviourProfileIncompatibleError(CAPBehaviourIntegrationError):
    """Raised when a BEP is not applicable to the CAP asset category."""


class CAPBehaviourIntegrationService:
    """Link CAP identities to production-authoritative Behaviour Profiles.

    CAPs persist stable BEP identities rather than exact versions. At production
    resolution time, each identity resolves through ``BehaviourProfileService``
    to the highest Canonical version, or otherwise the highest Approved version.
    """

    def __init__(self, caps: CAPService, behaviours: BehaviourProfileService) -> None:
        self.caps = caps
        self.behaviours = behaviours

    def available_for_cap(self, asset_id: str) -> tuple[BehaviourProfile, ...]:
        """Return production-authoritative BEPs compatible with one CAP asset."""
        cap = self.caps.get(asset_id)
        asset = self.caps.assets.get(cap.asset_id)
        profiles = self.behaviours.list(asset_category=asset.category)
        identities = tuple(dict.fromkeys(profile.profile_id for profile in profiles))
        resolved: list[BehaviourProfile] = []
        for profile_id in identities:
            profile = self.behaviours.production_profile(profile_id)
            if profile is None:
                continue
            if asset.category not in profile.applicable_asset_categories:
                continue
            resolved.append(profile)
        return tuple(
            sorted(resolved, key=lambda profile: (profile.name.lower(), profile.profile_id))
        )

    def resolve_for_cap(self, asset_id: str) -> tuple[BehaviourProfile, ...]:
        """Resolve all persisted CAP BEP identities to authoritative versions."""
        cap = self.caps.get(asset_id)
        asset = self.caps.assets.get(cap.asset_id)
        resolved: list[BehaviourProfile] = []
        for profile_id in cap.behaviour_references:
            profile = self.behaviours.production_profile(profile_id)
            if profile is None:
                raise BehaviourProfileUnavailableError(
                    f"CAP {cap.asset_id} references {profile_id}, but no Approved or Canonical "
                    "Behaviour Profile version is available"
                )
            if asset.category not in profile.applicable_asset_categories:
                raise BehaviourProfileIncompatibleError(
                    f"Behaviour Profile {profile.profile_id} is not applicable to "
                    f"asset category {asset.category.value}"
                )
            resolved.append(profile)
        return tuple(resolved)

    def set_behaviours(
        self,
        asset_id: str,
        profile_ids: tuple[str, ...],
    ) -> CanonicalAssetProfile:
        """Replace a CAP's BEP links after production-authority compatibility checks."""
        cap = self.caps.get(asset_id)
        asset = self.caps.assets.get(cap.asset_id)
        normalized = tuple(
            dict.fromkeys(
                profile_id.strip().upper() for profile_id in profile_ids if profile_id.strip()
            )
        )
        for profile_id in normalized:
            profile = self.behaviours.production_profile(profile_id)
            if profile is None:
                raise BehaviourProfileUnavailableError(
                    f"Behaviour Profile {profile_id} has no Approved or Canonical version"
                )
            if asset.category not in profile.applicable_asset_categories:
                raise BehaviourProfileIncompatibleError(
                    f"Behaviour Profile {profile.profile_id} is not applicable to "
                    f"asset category {asset.category.value}"
                )
        return self.caps.update(
            cap.asset_id,
            CAPUpdate(behaviour_references=normalized),
        )

    def link(self, asset_id: str, profile_id: str) -> CanonicalAssetProfile:
        """Link one BEP identity to a CAP without duplicating existing links."""
        cap = self.caps.get(asset_id)
        return self.set_behaviours(
            cap.asset_id,
            (*cap.behaviour_references, profile_id),
        )

    def unlink(self, asset_id: str, profile_id: str) -> CanonicalAssetProfile:
        """Remove one BEP identity from a CAP."""
        cap = self.caps.get(asset_id)
        normalized = profile_id.strip().upper()
        return self.set_behaviours(
            cap.asset_id,
            tuple(item for item in cap.behaviour_references if item != normalized),
        )
