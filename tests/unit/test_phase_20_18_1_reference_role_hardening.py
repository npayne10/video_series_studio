from __future__ import annotations

from vscs.application.acpp import (
    ProviderReadyReferenceResolver,
    ProviderReferenceCapabilities,
    ReferenceClass,
    ReferenceCoverage,
    ReferencePriority,
    ReferenceResolutionSeverity,
    ReferenceRole,
    ReferenceRoleRequest,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
)


class _Catalog:
    def __init__(self, records: dict[str, tuple[ShotReference, ...]]) -> None:
        self.records = records

    def references_for_asset(self, asset_id: str) -> tuple[ShotReference, ...]:
        return self.records.get(asset_id, ())


def _target() -> ReferenceTarget:
    return ReferenceTarget(
        width=1280,
        height=720,
        profile_id="production-video-16x9",
        provider_id="provider-local",
    )


def _reference(
    reference_id: str,
    *,
    role: ReferenceRole,
    asset_id: str | None = None,
    priority: ReferencePriority = ReferencePriority.REQUIRED,
    width: int = 1280,
    height: int = 720,
) -> ShotReference:
    return ShotReference(
        reference_id=reference_id,
        asset_id=asset_id,
        role=role,
        reference_class=ReferenceClass.PROVIDER_READY_DERIVATIVE,
        priority=priority,
        subject_type=(
            ReferenceSubjectType.MULTI_SUBJECT_SCENE
            if role is ReferenceRole.SCENE_COMPOSITION_ANCHOR
            else ReferenceSubjectType.CHARACTER
        ),
        source_path=f"references/{reference_id}.png",
        canonical_source_id=f"{asset_id}-MASTER" if asset_id else None,
        width=width,
        height=height,
        provider_ready=True,
        provider_profiles=("production-video-16x9",),
        coverage=ReferenceCoverage(
            framing_type="full_body",
            coverage="full_body",
            required_features_visible=True,
            identity_visible=True,
            full_required_asset_visible=True,
        ),
    )


def test_frame_anchor_requires_exact_target_dimensions() -> None:
    composition = _reference(
        "REF-COMPOSITION-HD",
        role=ReferenceRole.SCENE_COMPOSITION_ANCHOR,
        width=1920,
        height=1080,
    )
    resolver = ProviderReadyReferenceResolver(_Catalog({}))

    result = resolver.resolve(
        target=_target(),
        supplied_references=(composition,),
        requests=(
            ReferenceRoleRequest(
                role=ReferenceRole.SCENE_COMPOSITION_ANCHOR,
                priority=ReferencePriority.REQUIRED,
                preferred_reference_id="REF-COMPOSITION-HD",
            ),
        ),
    )

    assert not result.passed
    assert any(
        diagnostic.code == "REFERENCE_DIMENSIONS_MISMATCH"
        and diagnostic.severity is ReferenceResolutionSeverity.ERROR
        for diagnostic in result.diagnostics
    )


def test_supporting_identity_reference_can_use_provider_approved_same_aspect_size() -> None:
    identity = _reference(
        "REF-JAMES-HD",
        role=ReferenceRole.PRIMARY_IDENTITY,
        asset_id="CAP-CHR-001",
        width=1920,
        height=1080,
    )
    resolver = ProviderReadyReferenceResolver(_Catalog({"CAP-CHR-001": (identity,)}))

    result = resolver.resolve(
        target=_target(),
        requests=(
            ReferenceRoleRequest(
                role=ReferenceRole.PRIMARY_IDENTITY,
                priority=ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-001",
            ),
        ),
    )

    assert result.passed
    assert not any(
        diagnostic.code == "REFERENCE_DIMENSIONS_MISMATCH" for diagnostic in result.diagnostics
    )


def test_preferred_reference_must_fulfil_requested_role() -> None:
    wrong_role = _reference(
        "REF-JAMES-WRONG-ROLE",
        role=ReferenceRole.ENVIRONMENT_REFERENCE,
        asset_id="CAP-CHR-001",
    )
    resolver = ProviderReadyReferenceResolver(_Catalog({}))

    result = resolver.resolve(
        target=_target(),
        supplied_references=(wrong_role,),
        requests=(
            ReferenceRoleRequest(
                role=ReferenceRole.PRIMARY_IDENTITY,
                priority=ReferencePriority.REQUIRED,
                preferred_reference_id="REF-JAMES-WRONG-ROLE",
            ),
        ),
    )

    assert not result.passed
    assert any(diagnostic.code == "REFERENCE_ROLE_UNRESOLVED" for diagnostic in result.diagnostics)


def test_role_request_priority_governs_provider_binding() -> None:
    catalog_default_optional = _reference(
        "REF-JAMES",
        role=ReferenceRole.PRIMARY_IDENTITY,
        asset_id="CAP-CHR-001",
        priority=ReferencePriority.OPTIONAL,
    )
    resolver = ProviderReadyReferenceResolver(
        _Catalog({"CAP-CHR-001": (catalog_default_optional,)})
    )

    result = resolver.resolve(
        target=_target(),
        requests=(
            ReferenceRoleRequest(
                role=ReferenceRole.PRIMARY_IDENTITY,
                priority=ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-001",
            ),
        ),
        capabilities=ProviderReferenceCapabilities(
            provider_id="composition-only-provider",
            workflow_profile="i2v-start-frame",
            supported_roles=frozenset({ReferenceRole.SCENE_COMPOSITION_ANCHOR}),
        ),
    )

    assert result.plan.references[0].priority is ReferencePriority.REQUIRED
    assert not result.passed
    assert any(
        diagnostic.code == "PROVIDER_REQUIRED_ROLE_UNSUPPORTED" for diagnostic in result.diagnostics
    )
