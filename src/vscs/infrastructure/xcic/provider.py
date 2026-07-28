"""Canonical image provider backed by XCIC Core Rendering Library v1.0."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from vscs.domain.caps import CanonicalAssetGenerationRequest, GeneratedCanonicalAsset
from vscs.infrastructure.xcic.config import XCICConfiguration
from vscs.infrastructure.xcic_core import (
    XCICCoreClient,
    XCICCoreJob,
    XCICCoreRenderer,
    XCICCoreRenderingError,
    XCICCoreWorkflow,
)


class XCICImageProvider:
    """Generate canonical PNG candidates through the shared XCIC installation."""

    def __init__(
        self,
        project_directory: Path,
        *,
        configuration: XCICConfiguration | None = None,
    ) -> None:
        project = project_directory.expanduser().resolve(strict=False)
        config = configuration or XCICConfiguration.load()
        config.validate_text_to_image()
        workflow = XCICCoreWorkflow(
            workflow_id="xcic.qwen.text-to-image",
            editable_path=config.text_workflow_path,
            compiled_path=config.installation_root / "compiled" / "qwen_xcic_text_to_image_API.json",
            loader_class="XCICQueueJobLoader",
            queue_file_path=config.installation_root / "queues" / "xcic_generation_queue.json",
            quality_mode="standard",
            version="1.0",
        )
        self.renderer = XCICCoreRenderer(
            workflow,
            XCICCoreClient(config.comfyui_url),
        )
        self.output_root = project / "Render Cache" / "XCIC"

    def generate_images(
        self,
        asset_id: str,
        title: str,
        request: CanonicalAssetGenerationRequest,
    ) -> tuple[GeneratedCanonicalAsset, ...]:
        jobs: list[XCICCoreJob] = []
        for index in range(request.variations):
            seed = request.seed + index
            job_id = str(uuid4())
            filename = f"{asset_id}_xcic_{seed:010d}_{index + 1:02d}.png"
            jobs.append(
                XCICCoreJob(
                    job_id=job_id,
                    asset_id=asset_id,
                    positive_prompt=request.prompt,
                    negative_prompt=request.negative_prompt,
                    width=request.width,
                    height=request.height,
                    seed=seed,
                    steps=4,
                    cfg=1.0,
                    quality_mode="standard",
                    candidate_directory=self.output_root / asset_id.upper() / job_id,
                    candidate_filename=filename,
                    metadata={"title": title, "provider": "VSCS XCIC Core v1.0"},
                )
            )
        try:
            rendered = self.renderer.render(tuple(jobs))
        except XCICCoreRenderingError:
            raise
        return tuple(
            GeneratedCanonicalAsset(
                filename=result.output_path.name,
                media_type="image/png",
                content=result.output_path.read_bytes(),
                prompt=result.job.positive_prompt,
                negative_prompt=result.job.negative_prompt,
                model=request.model or result.workflow_id,
                seed=result.job.seed,
                width=result.job.width,
                height=result.job.height,
            )
            for result in rendered
        )
