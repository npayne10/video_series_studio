"""Canonical image provider that delegates rendering to XCIC and ComfyUI."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from vscs.domain.caps import CanonicalAssetGenerationRequest, GeneratedCanonicalAsset
from vscs.infrastructure.xcic.comfyui import ComfyUIClient
from vscs.infrastructure.xcic.config import XCICConfiguration
from vscs.infrastructure.xcic.engine import XCICRenderingEngine, XCICRenderingError
from vscs.infrastructure.xcic.models import (
    XCICGenerationJob,
    XCICWorkflowDefinition,
    XCICWorkflowKind,
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
        definition = XCICWorkflowDefinition(
            name="Qwen XCIC Text-to-Image",
            kind=XCICWorkflowKind.TEXT_TO_IMAGE,
            api_workflow_path=config.text_workflow_path,
            mapping_path=config.text_mapping_path,
            profile_path=config.text_profile_path,
            output_directory=project / "Render Cache" / "XCIC",
            version="2.0",
        )
        self.engine = XCICRenderingEngine(
            definition,
            ComfyUIClient(config.comfyui_url),
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
                    candidate_directory=(
                        self.engine.workflow.output_directory / asset_id.upper() / str(uuid4())
                    ),
                    candidate_filename=filename,
                    enable_turbo_mode=True,
                )
            )
        try:
            rendered = self.engine.render(tuple(jobs))
        except XCICRenderingError:
            raise
        return tuple(
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
            for output in rendered
        )
