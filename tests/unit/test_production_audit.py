"""Tests for Phase 14.6 production audit and provenance."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from vscs.application.acpp import (
    ACPPResolutionResult,
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    CompiledProductionPrompt,
    ContinuityBinding,
    OutputSpecification,
    ProductionBundle,
    PromptSpecification,
    RenderCapability,
    RenderInputReference,
    RenderJob,
    RenderQualityMode,
    RenderSpecification,
    RetryPolicy,
    SeedPolicy,
)
from vscs.application.production_pipeline import (
    AuditEventType,
    ExecutorErrorCode,
    ProductionAuditLedger,
    ProductionAuditSerializer,
    ProductionAuditService,
    ProductionAuditValidator,
    VersionedComponent,
    WorkerIdentity,
)
from vscs.application.production_pipeline.executors import ExecutionResult

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def _bundle() -> ProductionBundle:
    package = ClipProductionPackage(
        identity=ClipIdentity(
            clip_id="CLIP-001",
            production_id="PROD-001",
            episode_id="EP-001",
            scene_id="SC-001",
            shot_id="SH-001",
        ),
        render=RenderSpecification(1920, 800, 24, 240),
        assets=(
            AssetBinding(
                "CHR-JAMES",
                AssetBindingRole.SUBJECT,
                canonical_reference_ids=("REF-JAMES",),
            ),
        ),
        prompt=PromptSpecification("James stands on the bridge."),
        continuity=ContinuityBinding(),
        audio=AudioSpecification(),
        output=OutputSpecification("production", "clip-001"),
    )
    resolution = ACPPResolutionResult(package=package)
    prompt = CompiledProductionPrompt(
        clip_id="CLIP-001",
        schema_version="1.0",
        positive_prompt="James stands on the bridge.",
        negative_prompt="No drift.",
        canonical_reference_ids=("REF-JAMES",),
        prompt_package_ids=("PROMPT-BEHAVIOUR-001",),
        checksum="prompt-checksum",
    )
    job = RenderJob(
        job_id="JOB-001",
        clip_id="CLIP-001",
        width=1920,
        height=800,
        frames_per_second=24,
        frame_count=240,
        quality_mode=RenderQualityMode.PRODUCTION,
        seed_policy=SeedPolicy.FIXED,
        fixed_seed=42,
        positive_prompt=prompt.positive_prompt,
        negative_prompt=prompt.negative_prompt,
        input_references=(RenderInputReference("REF-JAMES", "canonical"),),
        start_reference_id=None,
        end_reference_id=None,
        output_path="production/clip-001.mp4",
        dependencies=(),
        retry_policy=RetryPolicy(),
        required_capabilities=(RenderCapability.TEXT_TO_VIDEO,),
        package_checksum="package-checksum",
        prompt_checksum="prompt-checksum",
    )
    return ProductionBundle(
        package=package,
        resolution=resolution,
        prompt=prompt,
        render_job=job,
        package_checksum="package-checksum",
        prompt_checksum="prompt-checksum",
        render_job_checksum="job-checksum",
        aggregate_checksum="bundle-checksum",
    )


def _provenance():
    worker = WorkerIdentity(
        worker_id="worker-a",
        executor_id="comfyui",
        capabilities=frozenset({RenderCapability.TEXT_TO_VIDEO}),
    )
    execution = ExecutionResult(
        job_id="JOB-001",
        worker_id="worker-a",
        succeeded=True,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=12),
        output_paths=("production/clip-001.mp4",),
    )
    return ProductionAuditService().capture(
        _bundle(),
        production_id="PROD-001",
        episode_id="EP-001",
        worker=worker,
        story_version="story-v3",
        ssie_version="ssie-v1",
        components=(
            VersionedComponent("model", "ltx-2.3", "22b-distilled"),
            VersionedComponent("workflow", "video-render", "5.0"),
        ),
        execution=execution,
        machine_metadata=(("gpu", "RTX-5090"),),
        captured_at=NOW,
    )


def test_capture_records_complete_provenance() -> None:
    provenance = _provenance()

    assert provenance.artifacts.asset_ids == ("CHR-JAMES",)
    assert provenance.artifacts.reference_ids == ("REF-JAMES",)
    assert provenance.artifacts.prompt_package_ids == ("PROMPT-BEHAVIOUR-001",)
    assert provenance.artifacts.components[0].component_id == "ltx-2.3"
    assert provenance.render.fixed_seed == 42
    assert provenance.render.duration_seconds == 12.0
    assert provenance.render.machine_metadata == (("gpu", "RTX-5090"),)


def test_append_builds_checksum_chain() -> None:
    service = ProductionAuditService()
    ledger = ProductionAuditLedger("LEDGER-001", "PROD-001")
    provenance = _provenance()
    ledger = service.append(
        ledger,
        event_type=AuditEventType.PROVENANCE_CAPTURED,
        actor_id="system",
        message="Captured production provenance",
        provenance=provenance,
        occurred_at=NOW,
    )
    ledger = service.append(
        ledger,
        event_type=AuditEventType.EXECUTION_COMPLETED,
        actor_id="worker-a",
        message="Render completed",
        provenance=provenance,
        occurred_at=NOW + timedelta(seconds=12),
    )

    assert ledger.entries[0].previous_checksum is None
    assert ledger.entries[1].previous_checksum == ledger.entries[0].checksum
    assert ProductionAuditValidator().validate(ledger).passed is True


def test_validator_detects_tampering() -> None:
    service = ProductionAuditService()
    ledger = service.append(
        ProductionAuditLedger("LEDGER-001", "PROD-001"),
        event_type=AuditEventType.EXECUTION_COMPLETED,
        actor_id="worker-a",
        message="Render completed",
        provenance=_provenance(),
        occurred_at=NOW,
    )
    tampered = replace(
        ledger,
        entries=(replace(ledger.entries[0], message="Changed after signing"),),
    )

    result = ProductionAuditValidator().validate(tampered)

    assert result.passed is False
    assert "ENTRY_CHECKSUM_MISMATCH" in {item.code for item in result.issues}


def test_json_round_trip_preserves_chain() -> None:
    service = ProductionAuditService()
    ledger = service.append(
        ProductionAuditLedger("LEDGER-001", "PROD-001"),
        event_type=AuditEventType.PROVENANCE_CAPTURED,
        actor_id="system",
        message="Captured provenance",
        provenance=_provenance(),
        occurred_at=NOW,
    )
    serializer = ProductionAuditSerializer()

    restored = serializer.loads(serializer.dumps(ledger))

    assert restored == ledger
    assert ProductionAuditValidator().validate(restored).passed is True


def test_query_filters_entries() -> None:
    service = ProductionAuditService()
    provenance = _provenance()
    ledger = ProductionAuditLedger("LEDGER-001", "PROD-001")
    ledger = service.append(
        ledger,
        event_type=AuditEventType.PROVENANCE_CAPTURED,
        actor_id="system",
        message="Captured provenance",
        provenance=provenance,
        occurred_at=NOW,
    )
    ledger = service.append(
        ledger,
        event_type=AuditEventType.EXECUTION_FAILED,
        actor_id="worker-a",
        message="Provider failed",
        provenance=provenance,
        occurred_at=NOW + timedelta(seconds=1),
    )

    matches = service.query(
        ledger,
        clip_id="CLIP-001",
        event_type=AuditEventType.EXECUTION_FAILED,
    )

    assert tuple(item.entry_id for item in matches) == ("AUDIT-00000002",)


def test_report_summarises_integrity_and_failures() -> None:
    service = ProductionAuditService()
    ledger = service.append(
        ProductionAuditLedger("LEDGER-001", "PROD-001"),
        event_type=AuditEventType.EXECUTION_FAILED,
        actor_id="worker-a",
        message=ExecutorErrorCode.PROVIDER_ERROR.value,
        provenance=_provenance(),
        occurred_at=NOW,
    )

    report = service.report(ledger)

    assert "Integrity: PASSED" in report
    assert "Execution failures: 1" in report
    assert "Entries: 1" in report
