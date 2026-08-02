"""Phase 15.6 end-to-end production pipeline integration test."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.acpp import (
    ACPPCompilerConfig,
    ACPPPromptCompiler,
    ACPPResolutionResult,
    ProductionBundleSerializer,
    ProductionBundleValidator,
    PromptCompilerConfig,
    RenderJobCompiler,
    SSIEToACPPCompiler,
)
from vscs.application.production_pipeline import (
    AuditEventType,
    ExecutorRegistry,
    ProductionAuditLedger,
    ProductionAuditService,
    ProductionAuditValidator,
    ProductionNode,
    ProductionPipeline,
    ProductionStage,
    ProductionState,
    QueuePriority,
    QueueState,
    RenderQueue,
    RenderQueueEntry,
    WorkerIdentity,
)
from vscs.application.ssie import (
    ProductionPlan,
    RuleBasedScenePlanner,
    Scene,
    SceneTransition,
)
from vscs.infrastructure.production import (
    AssetStager,
    AssetStagingConfig,
    ComfyUIClient,
    ComfyUIExecutorConfig,
    ComfyUIProductionExecutor,
    MediaProbeResult,
    RenderExecutionRequest,
    RenderExecutionService,
    RenderValidator,
    StagedAssetKind,
    StagingRequest,
    XCICCoreWorkflowCompiler,
)
from vscs.infrastructure.xcic_core.models import XCICCoreWorkflow

NOW = datetime.now(UTC)


class EmptyContributionCatalog:
    """Prompt catalog used when no behaviour contribution is required."""

    def resolve_prompt_package(self, package_id: str) -> None:
        del package_id
        return None


class SuccessfulComfyUIClient(ComfyUIClient):
    """ComfyUI transport double that produces the requested output file."""

    def __init__(self, output_path: Path) -> None:
        super().__init__(
            ComfyUIExecutorConfig(require_outputs=False),
            sleeper=lambda _seconds: None,
        )
        self.output_path = output_path
        self.submitted_workflow: dict[str, Any] | None = None

    def healthcheck(self) -> None:
        return None

    def submit(self, workflow: dict[str, Any]) -> str:
        self.submitted_workflow = workflow
        return "prompt-e2e-001"

    def wait(self, prompt_id: str) -> dict[str, Any]:
        assert prompt_id == "prompt-e2e-001"
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_bytes(b"VSCS synthetic rendered media")
        return {"outputs": {}}


class ExpectedMediaProbe:
    """Media probe double reporting the render-job contract exactly."""

    def __init__(self, width: int, height: int, fps: int, frames: int) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.frames = frames

    def probe(self, path: Path) -> MediaProbeResult:
        assert path.is_file()
        return MediaProbeResult(
            width=self.width,
            height=self.height,
            frame_rate=float(self.fps),
            frame_count=self.frames,
            duration_seconds=self.frames / self.fps,
            container="mp4",
            video_codec="synthetic",
            has_video=True,
        )


def _scene() -> Scene:
    return Scene(
        scene_id="SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        heading="INT. MAURITANIA OBSERVATION LOUNGE - NIGHT",
        location_asset_id="LOC-OBSERVATION-LOUNGE",
        summary="James watches an unexplained signal appear beyond the ship.",
        participant_asset_ids=("CHR-JAMES",),
        dialogue=(),
        required_asset_ids=(),
        time_of_day="night",
        transition_in=SceneTransition.CUT,
        estimated_duration_seconds=12.0,
    )


def test_complete_story_to_validated_render_and_audit_chain(tmp_path: Path) -> None:
    scene_plan = RuleBasedScenePlanner().plan_scene(_scene())
    production_plan = ProductionPlan(
        production_id="PROD-E2E",
        episode_id="EP-001",
        scene_plans=(scene_plan,),
    )
    acpp_compiler = SSIEToACPPCompiler(
        ACPPCompilerConfig(
            width=640,
            height=360,
            frames_per_second=24,
            output_root=str(tmp_path / "renders"),
        )
    )
    package = acpp_compiler.compile(production_plan)[0]
    resolution = ACPPResolutionResult(package=package)
    prompt = ACPPPromptCompiler(
        EmptyContributionCatalog(),
        PromptCompilerConfig(require_prompt_contributions=False),
    ).compile(resolution)
    render_compiler = RenderJobCompiler()
    job = render_compiler.compile(resolution, prompt)
    bundle = ProductionBundleSerializer().build(
        resolution,
        prompt,
        job,
        render_job_checksum=render_compiler.checksum(job),
        metadata={"test_scope": "phase-15.6"},
    )
    assert ProductionBundleValidator().validate(bundle).passed is True

    workflow_source = tmp_path / "workflow.json"
    workflow_compiled = tmp_path / "workflow.api.json"
    queue_path = tmp_path / "xcic" / "queue.json"
    workflow_source.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "XCICQueueLoader",
                    "inputs": {
                        "queue_file": "",
                        "job_index": 0,
                        "quality_mode": "production",
                    },
                },
                "2": {
                    "class_type": "SyntheticVideoOutput",
                    "inputs": {"source": ["1", 0]},
                },
            }
        ),
        encoding="utf-8",
    )
    xcic_compiler = XCICCoreWorkflowCompiler(
        XCICCoreWorkflow(
            workflow_id="WF-E2E",
            editable_path=workflow_source,
            compiled_path=workflow_compiled,
            loader_class="XCICQueueLoader",
            queue_file_path=queue_path,
            version="1.0",
        )
    )
    output_path = Path(job.output_path)
    client = SuccessfulComfyUIClient(output_path)
    executor = ComfyUIProductionExecutor(xcic_compiler, client)
    registry = ExecutorRegistry()
    registry.register(executor)

    staging_source = tmp_path / "model.bin"
    staging_source.write_bytes(b"synthetic model")
    stager = AssetStager(AssetStagingConfig(tmp_path / "staging"))
    service = RenderExecutionService(registry, stager=stager)
    queue = RenderQueue(
        queue_id="QUEUE-E2E",
        pipeline_id="PIPE-E2E",
        entries=(
            RenderQueueEntry(
                entry_id="ENTRY-E2E",
                job_id=job.job_id,
                clip_id=job.clip_id,
                state=QueueState.READY,
                priority=QueuePriority.HIGH,
                maximum_attempts=job.retry_policy.maximum_attempts,
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
    )
    pipeline = ProductionPipeline(
        pipeline_id="PIPE-E2E",
        production_id="PROD-E2E",
        episode_id="EP-001",
        nodes=(
            ProductionNode(
                node_id="RENDER-E2E",
                stage=ProductionStage.RENDERING,
                state=ProductionState.READY,
                clip_id=job.clip_id,
                artifact_id=job.job_id,
            ),
        ),
    )
    worker = WorkerIdentity(
        worker_id="worker-e2e",
        executor_id="comfyui",
        capabilities=executor.capabilities,
    )
    outcome = service.execute(
        RenderExecutionRequest(
            queue=queue,
            pipeline=pipeline,
            jobs=(job,),
            worker=worker,
            staging_requests=(
                StagingRequest(
                    asset_id="MODEL-E2E",
                    kind=StagedAssetKind.MODEL,
                    source_path=staging_source,
                ),
            ),
            entry_id="ENTRY-E2E",
        ),
        now=NOW,
    )

    assert outcome.entry.state is QueueState.COMPLETED
    assert outcome.execution_result is not None
    assert outcome.execution_result.succeeded is True
    render_node = outcome.pipeline.node("RENDER-E2E")
    assert render_node is not None
    assert render_node.state is ProductionState.COMPLETED
    assert outcome.staging_manifest is not None
    assert outcome.staging_manifest.artifact("MODEL-E2E") is not None
    assert queue_path.is_file()
    assert workflow_compiled.is_file()
    assert client.submitted_workflow is not None

    validation = RenderValidator(
        ExpectedMediaProbe(
            job.width,
            job.height,
            job.frames_per_second,
            job.frame_count,
        )
    ).validate(job, outcome.execution_result)
    assert validation.passed is True
    assert len(validation.outputs) == 1
    assert len(validation.outputs[0].checksum) == 64

    audit_service = ProductionAuditService()
    provenance = audit_service.capture(
        bundle,
        production_id="PROD-E2E",
        episode_id="EP-001",
        worker=worker,
        story_version="story-e2e-1",
        ssie_version="ssie-12.4",
        execution=outcome.execution_result,
        captured_at=NOW,
    )
    ledger = ProductionAuditLedger("LEDGER-E2E", "PROD-E2E")
    ledger = audit_service.append(
        ledger,
        event_type=AuditEventType.PROVENANCE_CAPTURED,
        actor_id="vscs",
        message="End-to-end provenance captured",
        provenance=provenance,
        occurred_at=NOW,
    )
    ledger = audit_service.append(
        ledger,
        event_type=AuditEventType.EXECUTION_COMPLETED,
        actor_id=worker.worker_id,
        message="End-to-end render completed and validated",
        provenance=provenance,
        occurred_at=outcome.execution_result.completed_at,
        metadata=(("validation_checksum", validation.outputs[0].checksum),),
    )

    assert ProductionAuditValidator().validate(ledger).passed is True
    assert ledger.entries[1].previous_checksum == ledger.entries[0].checksum
    assert bundle.package.identity.scene_id == scene_plan.scene.scene_id
    assert bundle.render_job.clip_id == package.identity.clip_id
