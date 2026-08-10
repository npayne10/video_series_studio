"""Application service and governance rules for Behaviour Profiles."""

from __future__ import annotations

import re

from vscs.application.behaviours.repository import (
    BehaviourProfileRepository,
    BehaviourProfileRepositoryError,
)
from vscs.domain.assets import AssetCategory
from vscs.domain.behaviours import (
    BehaviourAuthority,
    BehaviourCategory,
    BehaviourProfile,
    is_production_behaviour_authority,
)


class BehaviourProfileServiceError(RuntimeError):
    """Raised when a Behaviour Profile operation violates application governance."""


class BehaviourProfileNotFoundError(BehaviourProfileServiceError):
    """Raised when a requested Behaviour Profile version does not exist."""


class BehaviourGovernanceError(BehaviourProfileServiceError):
    """Raised when a requested authority transition or mutation is not permitted."""


_ALLOWED_TRANSITIONS: dict[BehaviourAuthority, frozenset[BehaviourAuthority]] = {
    BehaviourAuthority.DRAFT: frozenset({BehaviourAuthority.PROPOSED}),
    BehaviourAuthority.PROPOSED: frozenset({BehaviourAuthority.DRAFT, BehaviourAuthority.APPROVED}),
    BehaviourAuthority.APPROVED: frozenset({BehaviourAuthority.CANONICAL}),
    BehaviourAuthority.CANONICAL: frozenset(),
}


class BehaviourProfileService:
    """Govern creation, revision, authority and production resolution of BEPs."""

    def __init__(self, repository: BehaviourProfileRepository) -> None:
        self.repository = repository

    def create(self, profile: BehaviourProfile) -> BehaviourProfile:
        """Create a new governed Behaviour Profile version."""
        if profile.authority is not BehaviourAuthority.DRAFT:
            raise BehaviourGovernanceError(
                "New Behaviour Profile versions must enter governance as draft"
            )
        try:
            return self.repository.create(profile)
        except BehaviourProfileRepositoryError as exc:
            raise BehaviourProfileServiceError(str(exc)) from exc

    def get(self, profile_id: str, version: str) -> BehaviourProfile:
        """Return one exact Behaviour Profile version or raise a service error."""
        try:
            profile = self.repository.get(profile_id, version)
        except BehaviourProfileRepositoryError as exc:
            raise BehaviourProfileServiceError(str(exc)) from exc
        if profile is None:
            raise BehaviourProfileNotFoundError(
                f"Behaviour Profile {profile_id.strip().upper()} version {version.strip()} was not found"
            )
        return profile

    def list(
        self,
        *,
        query: str = "",
        category: BehaviourCategory | None = None,
        authority: BehaviourAuthority | None = None,
        asset_category: AssetCategory | None = None,
    ) -> tuple[BehaviourProfile, ...]:
        """List Behaviour Profiles through the governed application boundary."""
        try:
            return self.repository.list(
                query=query,
                category=category,
                authority=authority,
                asset_category=asset_category,
            )
        except BehaviourProfileRepositoryError as exc:
            raise BehaviourProfileServiceError(str(exc)) from exc

    def revise(
        self,
        profile_id: str,
        source_version: str,
        new_version: str,
    ) -> BehaviourProfile:
        """Create a new draft version from an existing profile without overwriting history."""
        source = self.get(profile_id, source_version)
        target_version = new_version.strip()
        if not target_version:
            raise BehaviourGovernanceError("A Behaviour Profile revision requires a version")
        if target_version == source.version:
            raise BehaviourGovernanceError("A Behaviour Profile revision requires a new version")
        revision = source.model_copy(
            update={"version": target_version, "authority": BehaviourAuthority.DRAFT}
        )
        return self.create(revision)

    def update_draft(self, profile: BehaviourProfile) -> BehaviourProfile:
        """Persist content edits only while an exact version remains draft."""
        current = self.get(profile.profile_id, profile.version)
        if current.authority is not BehaviourAuthority.DRAFT:
            raise BehaviourGovernanceError(
                "Only draft Behaviour Profile versions may be edited; create a revision instead"
            )
        if profile.authority is not BehaviourAuthority.DRAFT:
            raise BehaviourGovernanceError(
                "Authority changes must use the explicit governance transition operation"
            )
        try:
            updated = self.repository.update(profile)
        except BehaviourProfileRepositoryError as exc:
            raise BehaviourProfileServiceError(str(exc)) from exc
        if updated is None:
            raise BehaviourProfileNotFoundError(
                f"Behaviour Profile {profile.profile_id} version {profile.version} was not found"
            )
        return updated

    def transition(
        self,
        profile_id: str,
        version: str,
        target: BehaviourAuthority,
    ) -> BehaviourProfile:
        """Apply one explicit, auditable governance authority transition."""
        current = self.get(profile_id, version)
        if target is current.authority:
            return current
        if target not in _ALLOWED_TRANSITIONS[current.authority]:
            raise BehaviourGovernanceError(
                f"Behaviour Profile authority cannot transition from "
                f"{current.authority.value} to {target.value}"
            )
        transitioned = current.model_copy(update={"authority": target})
        try:
            updated = self.repository.update(transitioned)
        except BehaviourProfileRepositoryError as exc:
            raise BehaviourProfileServiceError(str(exc)) from exc
        if updated is None:
            raise BehaviourProfileNotFoundError(
                f"Behaviour Profile {profile_id.strip().upper()} version {version.strip()} was not found"
            )
        return updated

    def production_profile(self, profile_id: str) -> BehaviourProfile | None:
        """Resolve the highest production-authoritative version for one BEP identity."""
        try:
            versions = self.repository.list_versions(profile_id)
        except BehaviourProfileRepositoryError as exc:
            raise BehaviourProfileServiceError(str(exc)) from exc
        candidates = tuple(
            profile for profile in versions if is_production_behaviour_authority(profile.authority)
        )
        if not candidates:
            return None
        canonical = tuple(
            profile for profile in candidates if profile.authority is BehaviourAuthority.CANONICAL
        )
        pool = canonical or candidates
        return max(pool, key=lambda profile: _version_key(profile.version))

    def delete_draft(self, profile_id: str, version: str) -> bool:
        """Delete only disposable draft versions; governed history is retained."""
        profile = self.get(profile_id, version)
        if profile.authority is not BehaviourAuthority.DRAFT:
            raise BehaviourGovernanceError("Only draft Behaviour Profile versions may be deleted")
        try:
            return self.repository.delete(profile.profile_id, profile.version)
        except BehaviourProfileRepositoryError as exc:
            raise BehaviourProfileServiceError(str(exc)) from exc


def _version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    """Return a deterministic natural-sort key without imposing a versioning scheme."""
    parts = re.findall(r"\d+|[^\d]+", version.strip().lower())
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)
