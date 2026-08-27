"""Bind governed provider-ready reference plans into universal render requests."""

from __future__ import annotations

import json
from dataclasses import dataclass

from vscs.application.acpp import ReferencePlan, ReferenceRole, ShotReference
from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityPackageReference,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RendererKind,
    RenderRequest,
    RenderSettings,
)

from .package_compilation import CompiledProductionPackage


class ReferencePlanRenderBindingError(RuntimeError):
    """Raised when governed reference authority cannot be represented safely."""


@dataclass(frozen=True, slots=True)
class ReferencePlanRenderBinding:
    """Universal render request plus traceable reference-role decisions."""

    request: RenderRequest
    start_reference_id: str | None
    end_reference_id: str | None
    supporting_reference_ids: tuple[str, ...]


_START_ROLE_PRIORITY = (
    ReferenceRole.START_FRAME_REFERENCE,
    ReferenceRole.SCENE_COMPOSITION_ANCHOR,
    ReferenceRole.CONTINUITY_ANCHOR,
    ReferenceRole.PRIMARY_IDENTITY,
)
_SUPPORTING_ROLES = frozenset(
    {
        ReferenceRole.PRIMARY_IDENTITY,
        ReferenceRole.SECONDARY_IDENTITY,
        ReferenceRole.GROUP_IDENTITY,
        ReferenceRole.ENVIRONMENT_REFERENCE,
        ReferenceRole.BACKGROUND_IDENTITY,
        ReferenceRole.PROP_REFERENCE,
        ReferenceRole.FURNITURE_REFERENCE,
        ReferenceRole.STYLE_REFERENCE,
        ReferenceRole.MOTION_REFERENCE,
    }
)


class ReferencePlanRenderRequestBinder:
    """Translate a passed Phase 20.18.1 reference plan into renderer-neutral inputs."""

    def bind(
        self,
        package: CompiledProductionPackage,
        plan: ReferencePlan,
        *,
        workflow_id: str = "ltx23_production_v1",
        prompt_package_id: str | None = None,
    ) -> ReferencePlanRenderBinding:
        self._validate(package, plan)
        start = self._first_by_priority(plan, _START_ROLE_PRIORITY)
        end = self._single_optional(plan, ReferenceRole.END_FRAME_REFERENCE)
        supporting = tuple(
            reference
            for reference in plan.references
            if reference.role in _SUPPORTING_ROLES
            and reference.reference_id
            not in {
                start.reference_id if start is not None else None,
                end.reference_id if end is not None else None,
            }
        )
        metadata = {
            "positive_prompt": package.positive_prompt,
            "negative_prompt": package.negative_prompt,
            "authority_fingerprint": package.authority_fingerprint,
            "production_package_fingerprint": package.package_fingerprint,
            "reference_plan.schema_version": plan.schema_version,
            "reference_plan.reference_count": str(len(plan.references)),
            "reference_plan.role_manifest": self._role_manifest(plan),
        }
        if start is not None:
            metadata["start_frame"] = start.source_path
            metadata["reference_plan.start_reference_id"] = start.reference_id
        if end is not None:
            metadata["end_frame"] = end.source_path
            metadata["reference_plan.end_reference_id"] = end.reference_id
        if supporting:
            metadata["reference_images"] = json.dumps(
                [reference.source_path for reference in supporting],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            metadata["reference_plan.supporting_reference_ids"] = ",".join(
                reference.reference_id for reference in supporting
            )

        reference_ids = tuple(reference.reference_id for reference in plan.references)
        asset_ids = tuple(
            dict.fromkeys(
                reference.asset_id
                for reference in plan.references
                if reference.asset_id is not None and reference.asset_id.strip()
            )
        )
        request = RenderRequest(
            request_id=f"RR-{package.task_id}-{package.package_fingerprint[:12]}",
            production_id=package.production_id,
            container_id=package.episode_id,
            scene_id=package.scene_id or "UNSCOPED",
            shot_id=package.shot_id,
            clip_id=package.task_id,
            renderer=RendererKind.COMFYUI,
            workflow_id=workflow_id,
            quality_level=QualityLevel.PRODUCTION,
            prompt_package=PromptPackageReference(
                package_id=prompt_package_id or package.source_package_id,
                version=package.source_schema_version,
                checksum=package.source_package_fingerprint,
            ),
            assets=AssetPackageReference(
                asset_ids=asset_ids,
                canonical_reference_ids=reference_ids,
            ),
            continuity=ContinuityPackageReference(
                previous_frame_id=start.reference_id if start is not None else None,
                next_frame_id=end.reference_id if end is not None else None,
                requirements=("governed-reference-plan",),
                checksum=package.authority_fingerprint,
            ),
            render=RenderSettings(
                width=package.width,
                height=package.height,
                frames_per_second=package.frames_per_second,
                frame_count=package.frame_count,
                reference_strength=package.ic_lora_strength,
                seed=package.seed,
            ),
            output=OutputSettings(
                relative_directory="generated/provider_outputs",
                filename_stem=package.filename_prefix.replace("/", "_").replace("\\", "_"),
            ),
            metadata=metadata,
        )
        return ReferencePlanRenderBinding(
            request=request,
            start_reference_id=start.reference_id if start is not None else None,
            end_reference_id=end.reference_id if end is not None else None,
            supporting_reference_ids=tuple(reference.reference_id for reference in supporting),
        )

    @staticmethod
    def _validate(package: CompiledProductionPackage, plan: ReferencePlan) -> None:
        if plan.target.width != package.width or plan.target.height != package.height:
            raise ReferencePlanRenderBindingError(
                "ReferencePlan target dimensions do not match compiled production package"
            )
        if not plan.references:
            raise ReferencePlanRenderBindingError("ReferencePlan contains no governed references")
        reference_ids = [reference.reference_id for reference in plan.references]
        if len(set(reference_ids)) != len(reference_ids):
            raise ReferencePlanRenderBindingError("ReferencePlan contains duplicate reference IDs")
        for reference in plan.references:
            if not reference.provider_ready:
                raise ReferencePlanRenderBindingError(
                    f"Reference is not provider-ready: {reference.reference_id}"
                )
            if not reference.coverage.required_features_visible:
                raise ReferencePlanRenderBindingError(
                    f"Required reference features are not visible: {reference.reference_id}"
                )
            if not reference.coverage.full_required_asset_visible:
                raise ReferencePlanRenderBindingError(
                    f"Reference would require provider extrapolation: {reference.reference_id}"
                )

    @staticmethod
    def _first_by_priority(
        plan: ReferencePlan,
        roles: tuple[ReferenceRole, ...],
    ) -> ShotReference | None:
        for role in roles:
            candidates = plan.by_role(role)
            if candidates:
                return candidates[0]
        return None

    @staticmethod
    def _single_optional(plan: ReferencePlan, role: ReferenceRole) -> ShotReference | None:
        values = plan.by_role(role)
        if len(values) > 1:
            raise ReferencePlanRenderBindingError(
                f"ReferencePlan contains multiple {role.value} references"
            )
        return values[0] if values else None

    @staticmethod
    def _role_manifest(plan: ReferencePlan) -> str:
        payload = [
            {
                "reference_id": reference.reference_id,
                "asset_id": reference.asset_id,
                "role": reference.role.value,
                "class": reference.reference_class.value,
                "priority": reference.priority.value,
                "source_path": reference.source_path,
            }
            for reference in plan.references
        ]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
