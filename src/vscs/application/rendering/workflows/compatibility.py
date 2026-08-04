"""Render-request to workflow-manifest compatibility validation."""

from __future__ import annotations

from dataclasses import dataclass, fields

from vscs.application.rendering.capabilities import WorkflowCapabilities
from vscs.application.rendering.continuity import ContinuityPackage
from vscs.application.rendering.lip_sync import LipSyncMode, LipSyncRequest
from vscs.application.rendering.models import RenderRequest

from .diagnostics import (
    CompatibilityDiagnostic,
    CompatibilitySeverity,
    WorkflowCompatibilityReport,
)
from .manifest import (
    WorkflowManifest,
    WorkflowRequirement,
    WorkflowRequirementKind,
)


@dataclass(frozen=True, slots=True)
class InstalledWorkflowResources:
    """Resources currently available to a renderer installation."""

    checkpoints: frozenset[str] = frozenset()
    video_models: frozenset[str] = frozenset()
    loras: frozenset[str] = frozenset()
    vaes: frozenset[str] = frozenset()
    controlnets: frozenset[str] = frozenset()
    custom_nodes: frozenset[str] = frozenset()
    other: frozenset[str] = frozenset()

    def contains(self, requirement: WorkflowRequirement) -> bool:
        """Return whether one declared requirement is installed."""
        resources = {
            WorkflowRequirementKind.CHECKPOINT: self.checkpoints,
            WorkflowRequirementKind.VIDEO_MODEL: self.video_models,
            WorkflowRequirementKind.LORA: self.loras,
            WorkflowRequirementKind.VAE: self.vaes,
            WorkflowRequirementKind.CONTROLNET: self.controlnets,
            WorkflowRequirementKind.CUSTOM_NODE: self.custom_nodes,
            WorkflowRequirementKind.OTHER: self.other,
        }
        return requirement.identifier in resources[requirement.kind]


class WorkflowCompatibilityValidator:
    """Validate a renderer-neutral request against one workflow manifest."""

    def validate(
        self,
        request: RenderRequest,
        manifest: WorkflowManifest,
        *,
        installed: InstalledWorkflowResources | None = None,
        continuity: ContinuityPackage | None = None,
        lip_sync: LipSyncRequest | None = None,
    ) -> WorkflowCompatibilityReport:
        """Return structured compatibility findings without raising."""
        diagnostics: list[CompatibilityDiagnostic] = []
        self._validate_identity(request, manifest, diagnostics)
        self._validate_capabilities(request, manifest, diagnostics)
        self._validate_continuity(request, manifest, continuity, diagnostics)
        self._validate_lip_sync(request, manifest, lip_sync, diagnostics)
        self._validate_requirements(manifest, installed, diagnostics)
        if not diagnostics:
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.compatible",
                    CompatibilitySeverity.INFO,
                    "Workflow is compatible with the render request.",
                )
            )
        return WorkflowCompatibilityReport(
            workflow_id=manifest.workflow_id,
            request_id=request.request_id,
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def required_capabilities(request: RenderRequest) -> WorkflowCapabilities:
        """Infer workflow features required by one render request."""
        has_previous = request.continuity.previous_frame_id is not None
        has_next = request.continuity.next_frame_id is not None
        has_references = bool(request.assets.canonical_reference_ids)
        return WorkflowCapabilities(
            text_to_video=not has_previous,
            image_to_video=has_previous,
            start_frame=has_previous,
            end_frame=has_next,
            reference_images=has_references,
            multiple_reference_images=(
                len(request.assets.canonical_reference_ids) > 1
            ),
            loras=bool(request.assets.lora_ids),
            audio=request.voice.request_id is not None,
            lip_sync=request.lip_sync.required,
            seed_control=request.render.seed is not None,
        )

    @staticmethod
    def manifest_capabilities(manifest: WorkflowManifest) -> WorkflowCapabilities:
        """Convert manifest capability names into the typed capability model."""
        available = set(manifest.capabilities)
        known = {item.name for item in fields(WorkflowCapabilities)}
        return WorkflowCapabilities(**{name: name in available for name in known})

    def _validate_identity(
        self,
        request: RenderRequest,
        manifest: WorkflowManifest,
        diagnostics: list[CompatibilityDiagnostic],
    ) -> None:
        if request.renderer is not manifest.metadata.renderer:
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.renderer_mismatch",
                    CompatibilitySeverity.ERROR,
                    "Workflow renderer does not match the render request.",
                    manifest.metadata.renderer.value,
                )
            )
        if request.workflow_id != manifest.workflow_id:
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.identity_mismatch",
                    CompatibilitySeverity.ERROR,
                    "Render request targets a different workflow ID.",
                    request.workflow_id,
                )
            )
        if not manifest.supports_quality(request.quality_level):
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.quality_unsupported",
                    CompatibilitySeverity.ERROR,
                    "Workflow does not support the requested quality level.",
                    request.quality_level.value,
                )
            )

    def _validate_capabilities(
        self,
        request: RenderRequest,
        manifest: WorkflowManifest,
        diagnostics: list[CompatibilityDiagnostic],
    ) -> None:
        required = self.required_capabilities(request)
        available = self.manifest_capabilities(manifest)
        for capability in available.missing(required):
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.capability_missing",
                    CompatibilitySeverity.ERROR,
                    f"Workflow does not support required capability: {capability}.",
                    capability,
                )
            )
        known = {item.name for item in fields(WorkflowCapabilities)}
        for capability in sorted(set(manifest.capabilities) - known):
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.capability_unknown",
                    CompatibilitySeverity.WARNING,
                    f"Workflow declares an unknown capability: {capability}.",
                    capability,
                )
            )

    @staticmethod
    def _validate_continuity(
        request: RenderRequest,
        manifest: WorkflowManifest,
        continuity: ContinuityPackage | None,
        diagnostics: list[CompatibilityDiagnostic],
    ) -> None:
        if request.continuity.package_id and continuity is None:
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.continuity_unresolved",
                    CompatibilitySeverity.WARNING,
                    "A continuity package is referenced but was not supplied.",
                    request.continuity.package_id,
                )
            )
        if continuity is not None and continuity.shot_id != request.shot_id:
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.continuity_shot_mismatch",
                    CompatibilitySeverity.ERROR,
                    "Continuity package belongs to a different shot.",
                    continuity.shot_id,
                )
            )
        if (
            continuity is not None
            and continuity.previous_frame is not None
            and "start_frame" not in manifest.capabilities
        ):
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.continuity_start_frame_unsupported",
                    CompatibilitySeverity.ERROR,
                    "Workflow cannot consume the previous-shot boundary frame.",
                )
            )

    @staticmethod
    def _validate_lip_sync(
        request: RenderRequest,
        manifest: WorkflowManifest,
        lip_sync: LipSyncRequest | None,
        diagnostics: list[CompatibilityDiagnostic],
    ) -> None:
        if request.lip_sync.required and lip_sync is None:
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.lip_sync_unresolved",
                    CompatibilitySeverity.WARNING,
                    "A required lip-sync request was not supplied.",
                    request.lip_sync.request_id,
                )
            )
        if lip_sync is None:
            return
        if lip_sync.shot_id != request.shot_id:
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.lip_sync_shot_mismatch",
                    CompatibilitySeverity.ERROR,
                    "Lip-sync request belongs to a different shot.",
                    lip_sync.shot_id,
                )
            )
        if lip_sync.mode not in manifest.lip_sync_modes:
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.lip_sync_mode_unsupported",
                    CompatibilitySeverity.ERROR,
                    "Workflow does not support the requested lip-sync mode.",
                    lip_sync.mode.value,
                )
            )
        multi_modes = {
            LipSyncMode.ALTERNATING_SPEAKERS,
            LipSyncMode.MULTIPLE_SPEAKERS,
        }
        if (
            lip_sync.mode in multi_modes
            and "multiple_speakers" not in manifest.capabilities
        ):
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.multiple_speakers_unsupported",
                    CompatibilitySeverity.ERROR,
                    "Workflow does not support multiple visible speakers.",
                )
            )
        if (
            lip_sync.mode is LipSyncMode.PRECISION_CLOSE_UP
            and "precision_close_up" not in manifest.capabilities
        ):
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.precision_lip_sync_unsupported",
                    CompatibilitySeverity.ERROR,
                    "Workflow does not support precision close-up lip-sync.",
                )
            )

    @staticmethod
    def _validate_requirements(
        manifest: WorkflowManifest,
        installed: InstalledWorkflowResources | None,
        diagnostics: list[CompatibilityDiagnostic],
    ) -> None:
        if installed is None and manifest.requirements:
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.resources_unverified",
                    CompatibilitySeverity.WARNING,
                    "Workflow resource requirements were not checked.",
                )
            )
            return
        if installed is None:
            return
        for requirement in manifest.requirements:
            if installed.contains(requirement):
                continue
            severity = (
                CompatibilitySeverity.WARNING
                if requirement.optional
                else CompatibilitySeverity.ERROR
            )
            diagnostics.append(
                CompatibilityDiagnostic(
                    "workflow.resource_missing",
                    severity,
                    f"Required {requirement.kind.value} is not installed: "
                    f"{requirement.identifier}.",
                    requirement.identifier,
                )
            )
