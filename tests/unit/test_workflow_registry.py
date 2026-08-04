"""Tests for the workflow manifest registry."""

from __future__ import annotations

import pytest

from vscs.application.rendering import (
    DuplicateWorkflowManifestError,
    QualityLevel,
    RendererKind,
    WorkflowManifest,
    WorkflowManifestRegistryError,
    WorkflowMetadata,
    WorkflowRegistry,
)


def _manifest(
    workflow_id: str,
    *,
    renderer: RendererKind = RendererKind.COMFYUI,
    qualities: tuple[QualityLevel, ...] = (QualityLevel.PREVIEW,),
    tags: tuple[str, ...] = (),
) -> WorkflowManifest:
    return WorkflowManifest(
        metadata=WorkflowMetadata(
            workflow_id=workflow_id,
            display_name=workflow_id,
            description="",
            renderer=renderer,
            workflow_version="1.0",
        ),
        quality_levels=qualities,
        tags=tags,
    )


def test_workflow_registry_registers_filters_and_removes() -> None:
    registry = WorkflowRegistry()
    preview = _manifest("preview", tags=("ltx",))
    production = _manifest(
        "production",
        qualities=(QualityLevel.PRODUCTION,),
        tags=("ltx",),
    )
    flux = _manifest(
        "flux",
        renderer=RendererKind.FLUX,
        tags=("image",),
    )
    for manifest in (production, preview, flux):
        registry.register(manifest)

    assert registry.list() == (flux, preview, production)
    assert registry.list(renderer=RendererKind.COMFYUI) == (
        preview,
        production,
    )
    assert registry.list(quality_level=QualityLevel.PRODUCTION) == (
        production,
    )
    assert registry.list(tag="ltx") == (preview, production)
    assert registry.remove("preview") is preview
    assert registry.get("preview") is None


def test_workflow_registry_controls_duplicate_replacement() -> None:
    registry = WorkflowRegistry()
    original = _manifest("workflow")
    replacement = _manifest(
        "workflow",
        qualities=(QualityLevel.PRODUCTION,),
    )
    registry.register(original)

    with pytest.raises(DuplicateWorkflowManifestError, match="already"):
        registry.register(replacement)
    registry.register(replacement, replace=True)

    assert registry.require("workflow") is replacement
    with pytest.raises(WorkflowManifestRegistryError, match="not registered"):
        registry.require("missing")

    registry.clear()
    assert len(registry) == 0
