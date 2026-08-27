from __future__ import annotations

from dataclasses import replace

from vscs.application.acpp import (
    ACPPSerializer,
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    ProviderReadyReferenceResolver,
    ProviderReferenceCapabilities,
    ReferenceClass,
    ReferenceCoverage,
    ReferencePlan,
    ReferencePriority,
    ReferenceResolutionSeverity,
    ReferenceRole,
    ReferenceRoleRequest,
    ReferenceSubjectType,
    ReferenceTarget,
    RenderSpecification,
    ShotReference,
)


class _Catalog:
    def __init__(self, records: dict[str, tuple[ShotReference, ...]]) -> None:
        self.records = records

    def references_for_asset(self, asset_id: str) -> tuple[ShotReference, ...]:
        return self.records.get(asset_id, ())


def _reference(
    reference_id: str,
    *,
    asset_id: str,
    role: ReferenceRole,
    priority: ReferencePriority = ReferencePriority.REQUIRED,
    width: int = 1280,
    height: int = 720,
    provider_ready: bool = True,
    full_required_asset_visible: bool = True,
    identity_visible: bool = True,
) -> ShotReference:
    return ShotReference(
        reference_id=reference_id,
        asset_id=asset_id,
        role=role,
        reference_class=ReferenceClass.PROVIDER_READY_DERIVATIVE,
        priority=priority,
        subject_type=(
            ReferenceSubjectType.ENVIRONMENT
            if role is ReferenceRole.ENVIRONMENT_REFERENCE
            else ReferenceSubjectType.CHARACTER
        ),
        source_path=f"references/{reference_id}.png",
        canonical_source_id=f"{asset_id}-MASTER",
        width=width,
        height=height,
        provider_ready=provider_ready,
        provider_profiles=("production-video-16x9",),
        coverage=ReferenceCoverage(
            framing_type="full_body",
            coverage="full_body",
            required_features_visible=True,
            identity_visible=identity_visible,
            full_required_asset_visible=full_required_asset_visible,
        ),
        reference_fingerprint=f"fp-{reference_id}",
        file_checksum=f"sha-{reference_id}",
    )


def _target() -> ReferenceTarget:
    return ReferenceTarget(
        width=1280,
        height=720,
        profile_id="production-video-16x9",
        provider_id="provider-local",
    )


def _package() -> ClipProductionPackage:
    return ClipProductionPackage(
        identity=ClipIdentity(
            clip_id="CLIP-001",
            production_id="PROD-001",
            episode_id="E01",
            scene_id="S01",
            shot_id="SH01",
        ),
        render=RenderSpecification(
            width=1280,
            height=720,
            frames_per_second=24,
            frame_count=120,
        ),
        assets=(AssetBinding(asset_id="CAP-CHR-001", role=AssetBindingRole.SUBJECT),),
        prompt=PromptSpecification(positive_visual_intent="A controlled dialogue shot."),
        continuity=ContinuityBinding(),
        audio=AudioSpecification(),
        output=OutputSpecification(relative_directory="renders", filename_stem="clip-001"),
    )


def test_exact_profile_provider_ready_reference_resolves() -> None:
    james = _reference(
        "REF-JAMES",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
    )
    result = ProviderReadyReferenceResolver(_Catalog({"CAP-CHR-001": (james,)})).resolve(
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
    assert result.plan.references == (james,)


def test_required_aspect_mismatch_blocks_resolution() -> None:
    portrait = _reference(
        "REF-PORTRAIT",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
        width=1024,
        height=1536,
    )
    result = ProviderReadyReferenceResolver(_Catalog({"CAP-CHR-001": (portrait,)})).resolve(
        target=_target(),
        requests=(
            ReferenceRoleRequest(
                role=ReferenceRole.PRIMARY_IDENTITY,
                priority=ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-001",
            ),
        ),
    )

    assert not result.passed
    assert any(
        diagnostic.code == "REFERENCE_ASPECT_MISMATCH"
        and diagnostic.severity is ReferenceResolutionSeverity.ERROR
        for diagnostic in result.diagnostics
    )


def test_missing_full_asset_coverage_blocks_required_reference() -> None:
    cropped = _reference(
        "REF-CROPPED",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
        full_required_asset_visible=False,
    )
    result = ProviderReadyReferenceResolver(_Catalog({"CAP-CHR-001": (cropped,)})).resolve(
        target=_target(),
        requests=(
            ReferenceRoleRequest(
                role=ReferenceRole.PRIMARY_IDENTITY,
                priority=ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-001",
            ),
        ),
    )

    assert not result.passed
    assert any(
        diagnostic.code == "REFERENCE_EXTRAPOLATION_RISK" for diagnostic in result.diagnostics
    )


def test_multi_reference_dialogue_plan_resolves_all_required_roles() -> None:
    james = _reference(
        "REF-JAMES",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
    )
    cheryl = _reference(
        "REF-CHERYL",
        asset_id="CAP-CHR-002",
        role=ReferenceRole.SECONDARY_IDENTITY,
    )
    ros = _reference(
        "REF-ROS",
        asset_id="CAP-CHR-003",
        role=ReferenceRole.SECONDARY_IDENTITY,
    )
    room = _reference(
        "REF-ROOM",
        asset_id="CAP-LOC-001",
        role=ReferenceRole.ENVIRONMENT_REFERENCE,
    )
    resolver = ProviderReadyReferenceResolver(
        _Catalog(
            {
                "CAP-CHR-001": (james,),
                "CAP-CHR-002": (cheryl,),
                "CAP-CHR-003": (ros,),
                "CAP-LOC-001": (room,),
            }
        )
    )

    result = resolver.resolve(
        target=_target(),
        requests=(
            ReferenceRoleRequest(
                ReferenceRole.PRIMARY_IDENTITY,
                ReferencePriority.REQUIRED,
                "CAP-CHR-001",
            ),
            ReferenceRoleRequest(
                ReferenceRole.SECONDARY_IDENTITY,
                ReferencePriority.REQUIRED,
                "CAP-CHR-002",
            ),
            ReferenceRoleRequest(
                ReferenceRole.SECONDARY_IDENTITY,
                ReferencePriority.REQUIRED,
                "CAP-CHR-003",
            ),
            ReferenceRoleRequest(
                ReferenceRole.ENVIRONMENT_REFERENCE,
                ReferencePriority.REQUIRED,
                "CAP-LOC-001",
            ),
        ),
    )

    assert result.passed
    assert {reference.reference_id for reference in result.plan.references} == {
        "REF-JAMES",
        "REF-CHERYL",
        "REF-ROS",
        "REF-ROOM",
    }


def test_supported_provider_roles_bind_directly() -> None:
    james = _reference(
        "REF-JAMES",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
    )
    resolver = ProviderReadyReferenceResolver(_Catalog({"CAP-CHR-001": (james,)}))
    result = resolver.resolve(
        target=_target(),
        requests=(
            ReferenceRoleRequest(
                ReferenceRole.PRIMARY_IDENTITY,
                ReferencePriority.REQUIRED,
                "CAP-CHR-001",
            ),
        ),
        capabilities=ProviderReferenceCapabilities(
            provider_id="provider-local",
            workflow_profile="i2v-v1",
            supported_roles=frozenset({ReferenceRole.PRIMARY_IDENTITY}),
        ),
    )

    assert result.passed
    assert result.provider_binding is not None
    assert result.provider_binding.bindings == {"primary_identity": ("REF-JAMES",)}
    assert result.provider_binding.fallback_strategy is None


def test_unsupported_required_role_uses_scene_composition_fallback() -> None:
    james = _reference(
        "REF-JAMES",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
    )
    composition = ShotReference(
        reference_id="REF-COMPOSITION",
        role=ReferenceRole.SCENE_COMPOSITION_ANCHOR,
        reference_class=ReferenceClass.SHOT_COMPOSITE,
        priority=ReferencePriority.REQUIRED,
        subject_type=ReferenceSubjectType.MULTI_SUBJECT_SCENE,
        source_path="references/composition.png",
        width=1280,
        height=720,
        provider_ready=True,
        provider_profiles=("production-video-16x9",),
        coverage=ReferenceCoverage(
            framing_type="medium_wide",
            coverage="full_set",
            full_required_asset_visible=True,
        ),
    )
    resolver = ProviderReadyReferenceResolver(_Catalog({"CAP-CHR-001": (james,)}))
    result = resolver.resolve(
        target=_target(),
        supplied_references=(composition,),
        requests=(
            ReferenceRoleRequest(
                ReferenceRole.SCENE_COMPOSITION_ANCHOR,
                ReferencePriority.REQUIRED,
                preferred_reference_id="REF-COMPOSITION",
            ),
            ReferenceRoleRequest(
                ReferenceRole.PRIMARY_IDENTITY,
                ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-001",
            ),
        ),
        capabilities=ProviderReferenceCapabilities(
            provider_id="single-frame-provider",
            workflow_profile="i2v-start-frame",
            supported_roles=frozenset({ReferenceRole.SCENE_COMPOSITION_ANCHOR}),
            maximum_references=1,
        ),
    )

    assert result.passed
    assert result.provider_binding is not None
    assert result.provider_binding.fallback_strategy == "scene_composition_anchor"
    assert any(
        diagnostic.code == "PROVIDER_REFERENCE_FALLBACK" for diagnostic in result.diagnostics
    )


def test_unsupported_required_role_without_fallback_blocks_execution() -> None:
    james = _reference(
        "REF-JAMES",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
    )
    result = ProviderReadyReferenceResolver(_Catalog({"CAP-CHR-001": (james,)})).resolve(
        target=_target(),
        requests=(
            ReferenceRoleRequest(
                ReferenceRole.PRIMARY_IDENTITY,
                ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-001",
            ),
        ),
        capabilities=ProviderReferenceCapabilities(
            provider_id="composition-only-provider",
            workflow_profile="i2v-start-frame",
            supported_roles=frozenset({ReferenceRole.SCENE_COMPOSITION_ANCHOR}),
        ),
    )

    assert not result.passed
    assert any(
        diagnostic.code == "PROVIDER_REQUIRED_ROLE_UNSUPPORTED" for diagnostic in result.diagnostics
    )


def test_provider_reference_limit_is_enforced() -> None:
    james = _reference(
        "REF-JAMES",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
    )
    cheryl = _reference(
        "REF-CHERYL",
        asset_id="CAP-CHR-002",
        role=ReferenceRole.SECONDARY_IDENTITY,
    )
    resolver = ProviderReadyReferenceResolver(
        _Catalog({"CAP-CHR-001": (james,), "CAP-CHR-002": (cheryl,)})
    )
    result = resolver.resolve(
        target=_target(),
        requests=(
            ReferenceRoleRequest(
                ReferenceRole.PRIMARY_IDENTITY,
                ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-001",
            ),
            ReferenceRoleRequest(
                ReferenceRole.SECONDARY_IDENTITY,
                ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-002",
            ),
        ),
        capabilities=ProviderReferenceCapabilities(
            provider_id="limited-provider",
            workflow_profile="multi-ref-v1",
            supported_roles=frozenset(
                {ReferenceRole.PRIMARY_IDENTITY, ReferenceRole.SECONDARY_IDENTITY}
            ),
            maximum_references=1,
        ),
    )

    assert not result.passed
    assert any(
        diagnostic.code == "PROVIDER_REFERENCE_LIMIT_EXCEEDED" for diagnostic in result.diagnostics
    )


def test_reference_plan_round_trips_without_breaking_legacy_packages() -> None:
    serializer = ACPPSerializer()
    package = _package()

    legacy_payload = serializer.dumps(package)
    assert "reference_plan" not in legacy_payload
    assert serializer.loads(legacy_payload) == package

    james = _reference(
        "REF-JAMES",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
    )
    planned = replace(
        package,
        reference_plan=ReferencePlan(target=_target(), references=(james,)),
    )

    restored = serializer.loads(serializer.dumps(planned))
    assert restored.reference_plan == planned.reference_plan
    assert restored == planned
