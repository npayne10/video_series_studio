"""Resolve, migrate, and persist governed shot reference plans."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from vscs.application.acpp.reference_roles import (
    ProviderReadyReferenceResolver,
    ProviderReferenceCapabilities,
    ReferenceClass,
    ReferenceCoverage,
    ReferencePriority,
    ReferenceResolutionResult,
    ReferenceRole,
    ReferenceRoleRequest,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
)

from .governed_reference_plan_source import PersistedGovernedReferencePlanSource


class GovernedReferencePlanPersistenceError(RuntimeError):
    """Raised when legacy reference authority cannot be migrated safely."""


class GovernedReferencePlanPersistenceService:
    """Persist resolver-owned reference authority for live production projects."""

    def __init__(
        self,
        resolver: ProviderReadyReferenceResolver,
        store: PersistedGovernedReferencePlanSource,
    ) -> None:
        self.resolver = resolver
        self.store = store

    def resolve_and_persist(
        self,
        *,
        shot_id: str,
        target: ReferenceTarget,
        requests: tuple[ReferenceRoleRequest, ...],
        supplied_references: tuple[ShotReference, ...] = (),
        capabilities: ProviderReferenceCapabilities | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> ReferenceResolutionResult:
        """Resolve one governed plan and persist the exact resolver result.

        Failed resolution is persisted deliberately. This makes missing or unsuitable
        required authority durable and visible to downstream UPD/XPC compilation rather
        than silently falling back to loose canonical or legacy provider references.
        """
        resolution = self.resolver.resolve(
            target=target,
            requests=requests,
            supplied_references=supplied_references,
            capabilities=capabilities,
        )
        self.store.save_reference_plan(
            shot_id,
            self._resolution_payload(resolution),
            provenance=provenance,
        )
        return resolution

    def migrate_legacy_reference_plan(
        self,
        *,
        shot_id: str,
        target: ReferenceTarget,
        legacy_plan: dict[str, Any],
    ) -> ReferenceResolutionResult:
        """Conservatively migrate legacy schema 1.1 reference planning authority.

        Legacy canonical/provider references remain traceable, but are never promoted to
        provider-ready authority automatically. The first legacy identity becomes the
        primary identity and subsequent identities become secondary identities. Planet,
        location, and environment metadata assets become environment references.
        """
        schema_version = str(legacy_plan.get("schema_version") or "").strip()
        if schema_version != "1.1":
            raise GovernedReferencePlanPersistenceError(
                "Only legacy reference_plan schema 1.1 can be migrated explicitly"
            )

        supplied: list[ShotReference] = []
        requests: list[ReferenceRoleRequest] = []

        identity_raw = legacy_plan.get("identity_references", [])
        if not isinstance(identity_raw, list):
            raise GovernedReferencePlanPersistenceError(
                "Legacy identity_references must be a JSON array"
            )
        for index, item in enumerate(identity_raw):
            if not isinstance(item, dict):
                continue
            role = ReferenceRole.PRIMARY_IDENTITY if index == 0 else ReferenceRole.SECONDARY_IDENTITY
            reference = self._legacy_reference(
                item,
                role=role,
                subject_type=ReferenceSubjectType.CHARACTER,
                reference_id_prefix="LEGACY-IDENTITY",
            )
            supplied.append(reference)
            requests.append(
                ReferenceRoleRequest(
                    role=role,
                    priority=ReferencePriority.REQUIRED,
                    asset_id=reference.asset_id,
                    preferred_reference_id=reference.reference_id,
                )
            )

        metadata_raw = legacy_plan.get("metadata_assets", [])
        if not isinstance(metadata_raw, list):
            raise GovernedReferencePlanPersistenceError(
                "Legacy metadata_assets must be a JSON array"
            )
        for item in metadata_raw:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "").strip().lower()
            if category not in {"planet", "location", "environment", "set"}:
                continue
            reference = self._legacy_reference(
                item,
                role=ReferenceRole.ENVIRONMENT_REFERENCE,
                subject_type=ReferenceSubjectType.ENVIRONMENT,
                reference_id_prefix="LEGACY-ENVIRONMENT",
            )
            supplied.append(reference)
            requests.append(
                ReferenceRoleRequest(
                    role=ReferenceRole.ENVIRONMENT_REFERENCE,
                    priority=ReferencePriority.REQUIRED,
                    asset_id=reference.asset_id,
                    preferred_reference_id=reference.reference_id,
                )
            )

        if not requests:
            raise GovernedReferencePlanPersistenceError(
                "Legacy reference plan contains no migratable governed reference authority"
            )

        return self.resolve_and_persist(
            shot_id=shot_id,
            target=target,
            requests=tuple(requests),
            supplied_references=tuple(supplied),
            provenance={
                "source": "legacy_reference_plan",
                "source_schema_version": schema_version,
                "migration_policy": "conservative-no-provider-ready-upgrade",
            },
        )

    @staticmethod
    def _legacy_reference(
        raw: dict[str, Any],
        *,
        role: ReferenceRole,
        subject_type: ReferenceSubjectType,
        reference_id_prefix: str,
    ) -> ShotReference:
        asset_id = str(raw.get("asset_id") or "").strip() or None
        source_path = str(raw.get("image") or "").strip()
        if not source_path:
            raise GovernedReferencePlanPersistenceError(
                "Legacy reference authority is missing its image path"
            )
        fingerprint = str(raw.get("reference_fingerprint") or "").strip() or None
        checksum = str(raw.get("file_checksum") or "").strip() or None
        identity = asset_id or fingerprint or checksum or "UNIDENTIFIED"
        reference_id = f"{reference_id_prefix}-{identity}"
        return ShotReference(
            reference_id=reference_id,
            asset_id=asset_id,
            role=role,
            reference_class=ReferenceClass.CANONICAL_MASTER,
            priority=ReferencePriority.REQUIRED,
            subject_type=subject_type,
            source_path=source_path,
            canonical_source_id=asset_id,
            label="Migrated legacy reference authority",
            width=0,
            height=0,
            provider_ready=False,
            provider_profiles=(),
            coverage=ReferenceCoverage(
                framing_type="unknown",
                coverage="unknown",
                required_features_visible=False,
                identity_visible=False,
                full_required_asset_visible=False,
            ),
            reference_fingerprint=fingerprint,
            file_checksum=checksum,
        )

    @staticmethod
    def _resolution_payload(resolution: ReferenceResolutionResult) -> dict[str, Any]:
        plan = resolution.plan
        return {
            "schema_version": plan.schema_version,
            "status": "passed" if resolution.passed else "failed",
            "target": {
                "width": plan.target.width,
                "height": plan.target.height,
                "profile_id": plan.target.profile_id,
                "provider_id": plan.target.provider_id,
                "aspect_tolerance": plan.target.aspect_tolerance,
            },
            "references": [GovernedReferencePlanPersistenceService._reference_payload(item) for item in plan.references],
            "diagnostics": [
                {
                    "severity": item.severity.value,
                    "code": item.code,
                    "message": item.message,
                    "reference_id": item.reference_id,
                }
                for item in resolution.diagnostics
            ],
        }

    @staticmethod
    def _reference_payload(reference: ShotReference) -> dict[str, Any]:
        payload = asdict(reference)
        payload["role"] = reference.role.value
        payload["reference_class"] = reference.reference_class.value
        payload["priority"] = reference.priority.value
        payload["subject_type"] = reference.subject_type.value
        payload["provider_profiles"] = list(reference.provider_profiles)
        payload["contains_subjects"] = list(reference.contains_subjects)
        payload["contains_props"] = list(reference.contains_props)
        payload["contains_environments"] = list(reference.contains_environments)
        return payload
