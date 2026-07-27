"""Canonical image provider that delegates rendering to XCIC and ComfyUI."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from vscs.domain.caps import CanonicalAssetGenerationRequest, GeneratedCanonicalAsset
from vscs.infrastructure.xcic.comfyui import ComfyUIClient
from vscs.infrastructure.xcic.engine import XCICRenderingEngine, XCICRenderingError
from vscs.infrastructure.xcic.models import (
    XCICGenerationJob,
    XCICWorkflowDefinition,
    XCICWorkflowKind,
)


class XCICImageProvider:
    """Generate real canonical PNG candidates through a configured XCIC workflow."""

    def __init__(
        self,
        project_directory: Path,
        *,
        workflow_path: Path | None = None,
        comfyui_url: str | None = None,
    ) -> None:
        project = project_directory.expanduser().resolve(strict=False)
        xcic_root = project / "XCIC"
        workflow = workflow_path or Path(
            os.environ.get(
                "VSCS_XCIC_TEXT_WORKFLOW",
                str(xcic_root / "Workflows" / "Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json"),
            )
        )
        definition = XCICWorkflowDefinition(
            name="Qwen XCIC Text-to-Image",
            kind=XCICWorkflowKind.TEXT_TO_IMAGE,
            api_workflow_path=workflow,
            queue_file_path=xcic_root / "Queues" / "xcic_generation_queue.json",
            output_directory=xcic_root / "Candidates",
            version="1.0",
        )
        self.engine = XCICRenderingEngine(
            definition,
            ComfyUIClient(comfyui_url or os.environ.get("VSCS_COMFYUI_URL", "http://127.0.0.1:8188")),
        )

    def generate_images(
        self,
        asset_id: str,
        title: str,
        request: CanonicalAssetGenerationRequest,
    ) -> tuple[GeneratedCanonicalAsset, ...]:
        jobs: list[XCICGenerationJob] = []
        for index in range(request.variations):
            seed = request.seed + index
            filename = f"{asset_id}_xcic_{seed:010d}_{index + 1:02d}.png"
            jobs.append(
                XCICGenerationJob(
                    job_id=str(uuid4()),
                    asset_id=asset_id,
                    positive_prompt=request.prompt,
                    negative_prompt=request.negative_prompt,
                    width=request.width,
                    height=request.height,
                    seed=seed,
                    steps=4,
                    cfg=1.0,
                    candidate_directory=self.engine.workflow.output_directory / asset_id.upper(),
                    candidate_filename=filename,
                    enable_turbo_mode=True,
                )
            )
        try:
            rendered = self.engine.render(tuple(jobs))
        except XCICRenderingError:
            raise
        values: list[GeneratedCanonicalAsset] = []
        for output in rendered:
            values.append(
                GeneratedCanonicalAsset(
                    filename=output.path.name,
                    media_type="image/png",
                    content=output.path.read_bytes(),
                    prompt=output.job.positive_prompt,
                    negative_prompt=output.job.negative_prompt,
                    model=request.model or output.workflow_name,
                    seed=output.job.seed,
                    width=output.job.width,
                    height=output.job.height,
                )
            )
        return tuple(values)
