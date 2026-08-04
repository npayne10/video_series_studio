"""Tests for render job lifecycle and output provenance."""

from datetime import UTC, datetime

import pytest

from vscs.application.rendering import (
    QualityLevel,
    RendererKind,
    RenderJob,
    RenderJobStatus,
    RenderOutput,
    RenderOutputKind,
)


def test_render_job_allows_valid_lifecycle_transitions() -> None:
    job = RenderJob(job_id="JOB-001", request_id="REQ-001")
    preparing = job.transition(
        RenderJobStatus.PREPARING,
        submitted_at=datetime.now(UTC),
    )
    running = preparing.transition(
        RenderJobStatus.RUNNING,
        progress=0.5,
        renderer_job_id="remote-001",
    )
    completed = running.transition(
        RenderJobStatus.COMPLETED,
        progress=1.0,
        finished_at=datetime.now(UTC),
    )

    assert completed.status is RenderJobStatus.COMPLETED
    assert completed.progress == 1.0
    with pytest.raises(ValueError, match="Invalid render job transition"):
        completed.transition(RenderJobStatus.RUNNING)


def test_render_output_records_complete_provenance() -> None:
    output = RenderOutput(
        output_id="OUT-001",
        kind=RenderOutputKind.PREVIEW_VIDEO,
        relative_path="renders/EP-001/preview.mp4",
        request_id="REQ-001",
        renderer=RendererKind.COMFYUI,
        workflow_id="ltx-preview-v1",
        quality_level=QualityLevel.PREVIEW,
    )

    assert output.request_id == "REQ-001"
    assert output.renderer is RendererKind.COMFYUI
    assert output.created_at.tzinfo is UTC
