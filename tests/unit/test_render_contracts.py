"""Tests for renderer capabilities and adapter registration."""

from vscs.application.rendering import (
    RenderAdapterRegistry,
    RendererKind,
    WorkflowCapabilities,
)


def test_workflow_capability_matching_reports_missing_features() -> None:
    available = WorkflowCapabilities(
        image_to_video=True,
        start_frame=True,
        reference_images=True,
        seed_control=True,
    )
    required = WorkflowCapabilities(
        image_to_video=True,
        start_frame=True,
        end_frame=True,
        reference_images=True,
    )

    assert not available.supports(required)
    assert available.missing(required) == ("end_frame",)


def test_adapter_registry_starts_empty() -> None:
    registry = RenderAdapterRegistry()

    assert registry.renderers() == ()
    assert not registry.contains(RendererKind.COMFYUI)
