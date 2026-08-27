from __future__ import annotations

from types import SimpleNamespace

from vscs.application.acpp import (
    ReferenceClass,
    ReferenceCoverage,
    ReferencePlan,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
)
from vscs.application.production_execution import (
    CompiledProductionPackage,
    LiveShotFunctionalAcceptanceService,
)


def _package() -> CompiledProductionPackage:
    return CompiledProductionPackage(
        task_id="TASK-001",
        production_id="PROD-001",
        episode_id="E01",
        scene_id="S01",
        shot_id="SH01",
        profile="production",
        authority_id="AUTH-001",
        authority_revision=1,
        authority_fingerprint="AUTH-FP",
        approved_by="human:operator",
        source_package_id="PKG-001",
        source_package_fingerprint="PKG-FP",
        source_schema_version="1.0",
        universal_text="Governed live shot.",
        positive_prompt="Governed live shot.",
        negative_prompt="identity drift",
        previous_approved_final_frame=None,
        filename_prefix="PROD-001/E01/TASK-001",
        width=1280,
        height=720,
        frame_count=121,
        frames_per_second=25,
        cfg=1.0,
        ic_lora_strength=1.0,
        seed=424242,
        composition_plan={},
        production_authority={},
        package_fingerprint="PACKAGE-FP",
    )


def _plan() -> ReferencePlan:
    return ReferencePlan(
        target=ReferenceTarget(
            width=1280,
            height=720,
            profile_id="production-video-16x9",
            provider_id="ltx23-local",
        ),
        references=(
            ShotReference(
                reference_id="REF-JAMES",
                asset_id="CAP-CHR-001",
                role=ReferenceRole.PRIMARY_IDENTITY,
                reference_class=ReferenceClass.PROVIDER_READY_DERIVATIVE,
                priority=ReferencePriority.REQUIRED,
                subject_type=ReferenceSubjectType.CHARACTER,
                source_path="references/james-1280x720.png",
                width=1280,
                height=720,
                provider_ready=True,
                coverage=ReferenceCoverage(
                    framing_type="full_body",
                    coverage="full_body",
                    required_features_visible=True,
                    identity_visible=True,
                    full_required_asset_visible=True,
                ),
            ),
        ),
    )


class _Execution:
    def __init__(self) -> None:
        self.submitted_request = None

    def submit(self, queue, entry_id, worker_id, render_request, production_package, **kwargs):
        del queue, entry_id, worker_id, production_package, kwargs
        self.submitted_request = render_request
        return SimpleNamespace(submitted=True)

    def reconcile(self, queue, entry_id, lease_id, handle, **kwargs):
        del queue, entry_id, lease_id, kwargs
        return SimpleNamespace(
            terminal=True,
            handle=handle,
            outputs=(SimpleNamespace(output_id="OUT-001"),),
            execution_job=SimpleNamespace(execution_id="EXEC-001"),
        )


class _Ingestion:
    def __init__(self) -> None:
        self.calls = []

    def ingest_execution_outputs(self, execution_job, task, outputs):
        self.calls.append((execution_job, task, outputs))
        return (SimpleNamespace(media=SimpleNamespace(media_id="GM-001"), created=True),)


def test_governed_reference_plan_reaches_provider_and_completed_output_is_ingested() -> None:
    execution = _Execution()
    ingestion = _Ingestion()
    service = LiveShotFunctionalAcceptanceService(execution=execution, ingestion=ingestion)
    task = SimpleNamespace(task_id="TASK-001", authority=SimpleNamespace(fingerprint="AUTH-FP"))

    submitted = service.submit(
        queue=SimpleNamespace(),
        entry_id="ENTRY-001",
        worker_id="WORKER-001",
        task=task,
        package=_package(),
        reference_plan=_plan(),
        production_package_path="packages/TASK-001.json",
        lease_duration_seconds=300.0,
        provider_id="ltx23-local",
    )

    assert submitted.submitted
    assert execution.submitted_request is not None
    assert execution.submitted_request.workflow_id == "ltx23_production_v1"
    assert execution.submitted_request.metadata["start_frame"] == "references/james-1280x720.png"

    handle = SimpleNamespace(state=SimpleNamespace(value="completed"))
    reconciled = service.reconcile(
        queue=SimpleNamespace(),
        entry_id="ENTRY-001",
        lease_id="LEASE-001",
        handle=handle,
        task=task,
        lease_duration_seconds=300.0,
    )

    assert reconciled.completed
    assert len(reconciled.generated_media) == 1
    assert reconciled.generated_media[0].media.media_id == "GM-001"
    assert len(ingestion.calls) == 1
