"""Integration contract for RenderOutput versus authoritative Generated Media."""

from vscs.application.rendering import (
    QualityLevel,
    RendererKind,
    RenderOutput,
    RenderOutputKind,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
    GeneratedMediaState,
)


def test_render_output_remains_execution_result_while_generated_media_owns_production_authority() -> (
    None
):
    output = RenderOutput(
        output_id="OUT-001",
        kind=RenderOutputKind.PRODUCTION_VIDEO,
        relative_path="provider-output/clip.mp4",
        request_id="REQ-001",
        renderer=RendererKind.COMFYUI,
        workflow_id="LTX-VIDEO-PRODUCTION",
        quality_level=QualityLevel.PRODUCTION,
        checksum="b" * 64,
    )

    media = GeneratedMedia(
        media_id="GM-PROD-001-SHT-001-0001",
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="PROD-001",
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
            production_task_id="PT-VIDEO-001",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id="EXEC-001",
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id="PROMPT-001",
            render_request_id=output.request_id,
            render_output_id=output.output_id,
            workflow_id=output.workflow_id,
        ),
        file=GeneratedMediaFile(
            relative_path="generated_media/video/EP-001/SCN-001/SHT-001/clip.mp4",
            checksum_sha256=output.checksum,
        ),
    )

    assert output.renderer is RendererKind.COMFYUI
    assert output.relative_path == "provider-output/clip.mp4"
    assert media.state is GeneratedMediaState.GENERATED
    assert media.scope.production_task_id == "PT-VIDEO-001"
    assert media.provenance.render_output_id == output.output_id
    assert media.file.relative_path != output.relative_path
