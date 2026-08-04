"""Registry for installed workflow manifests."""

from __future__ import annotations

from dataclasses import dataclass, field

from vscs.application.rendering.models import QualityLevel, RendererKind

from .manifest import WorkflowManifest


class WorkflowManifestRegistryError(RuntimeError):
    """Base workflow-registry failure."""


class DuplicateWorkflowManifestError(WorkflowManifestRegistryError):
    """Raised when duplicate registration is disallowed."""


@dataclass(slots=True)
class WorkflowRegistry:
    """Authoritative in-memory catalogue of workflow manifests."""

    _manifests: dict[str, WorkflowManifest] = field(default_factory=dict)

    def register(
        self,
        manifest: WorkflowManifest,
        *,
        replace: bool = False,
    ) -> None:
        """Register one workflow manifest by stable identity."""
        workflow_id = manifest.workflow_id
        if workflow_id in self._manifests and not replace:
            raise DuplicateWorkflowManifestError(
                f"Workflow manifest already registered: {workflow_id}"
            )
        self._manifests[workflow_id] = manifest

    def remove(self, workflow_id: str) -> WorkflowManifest | None:
        """Remove and return one manifest when present."""
        return self._manifests.pop(workflow_id, None)

    def get(self, workflow_id: str) -> WorkflowManifest | None:
        """Return one workflow manifest by identity."""
        return self._manifests.get(workflow_id)

    def require(self, workflow_id: str) -> WorkflowManifest:
        """Return one workflow manifest or raise a registry error."""
        manifest = self.get(workflow_id)
        if manifest is None:
            raise WorkflowManifestRegistryError(
                f"Workflow manifest is not registered: {workflow_id}"
            )
        return manifest

    def list(
        self,
        *,
        renderer: RendererKind | None = None,
        quality_level: QualityLevel | None = None,
        tag: str | None = None,
    ) -> tuple[WorkflowManifest, ...]:
        """List manifests in stable identity order using basic filters."""
        manifests = self._manifests.values()
        return tuple(
            sorted(
                (
                    manifest
                    for manifest in manifests
                    if (
                        renderer is None
                        or manifest.metadata.renderer is renderer
                    )
                    and (
                        quality_level is None
                        or manifest.supports_quality(quality_level)
                    )
                    and (tag is None or tag in manifest.tags)
                ),
                key=lambda manifest: manifest.workflow_id,
            )
        )

    def clear(self) -> None:
        """Remove every registered workflow manifest."""
        self._manifests.clear()

    def __len__(self) -> int:
        return len(self._manifests)
