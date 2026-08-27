from __future__ import annotations

from vscs.application.acpp import (
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    ProviderReadyReferenceResolver,
    ReferenceClass,
    ReferenceCoverage,
    ReferencePlanApplicationService,
    ReferencePriority,
    ReferenceRole,
    ReferenceRoleRequest,
    ReferenceSubjectType,
    RenderSpecification,
    ShotReference,
)


class _Catalog:
    def __init__(self, reference: ShotReference) -> None:
        self.reference = reference

    def references_for_asset(self, asset_id: str) -> tuple[ShotReference, ...]:
        if asset_id == self.reference.asset_id:
            return (self.reference,)
        return ()


def _package() -> ClipProductionPackage:
    return ClipProductionPackage(
        identity=ClipIdentity(
            clip_id="CLIP-REFERENCE-PLAN",
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
        prompt=PromptSpecification(positive_visual_intent="James remains stable."),
        continuity=ContinuityBinding(),
        audio=AudioSpecification(),
        output=OutputSpecification(relative_directory="renders", filename_stem="clip"),
    )


def test_application_service_attaches_resolved_reference_plan() -> None:
    reference = ShotReference(
        reference_id="REF-JAMES-VIDEO",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
        reference_class=ReferenceClass.PROVIDER_READY_DERIVATIVE,
        priority=ReferencePriority.REQUIRED,
        subject_type=ReferenceSubjectType.CHARACTER,
        source_path="references/james-video.png",
        canonical_source_id="CAP-CHR-001-MASTER",
        width=1280,
        height=720,
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
    service = ReferencePlanApplicationService(
        ProviderReadyReferenceResolver(_Catalog(reference))
    )

    result = service.resolve_package(
        _package(),
        profile_id="production-video-16x9",
        provider_id="ltx23-local",
        requests=(
            ReferenceRoleRequest(
                role=ReferenceRole.PRIMARY_IDENTITY,
                priority=ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-001",
            ),
        ),
    )

    assert result.passed
    assert result.package.reference_plan is not None
    assert result.package.reference_plan.target.width == 1280
    assert result.package.reference_plan.target.height == 720
    assert result.package.reference_plan.references == (reference,)
    assert result.package.metadata["reference_plan.status"] == "resolved"
    assert result.package.metadata["reference_plan.reference_count"] == "1"
