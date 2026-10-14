"""Phase 20.18.2.3.6.6b.5 accepted-provider reconciliation regressions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    GeneratedMediaSelection,
    GeneratedMediaSelectionEvent,
)
from vscs.application.production_execution import (
    ProviderExecutionReadiness,
    ProviderExecutionReadinessState,
)
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.generated_media.technical_validation import TechnicalMediaObservation
from vscs.domain.generated_media import GeneratedMediaKind
from vscs.infrastructure.generated_media import (
    JsonGeneratedMediaRepository,
    JsonGeneratedMediaSelectionRepository,
)
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository
from vscs.infrastructure.production_execution.accepted_provider_media_reconciliation import (
    AcceptedProviderProductionReconciliationService,
)
from vscs.infrastructure.production_execution.minimax_h3_functional_acceptance import (
    MiniMaxH3MediaObservation,
)
from vscs.infrastructure.production_execution.provider_production_adoption_store import (
    ProviderProductionAdoptionStore,
)

TASK_ID = "PT-VIDEO-GENERATION-29A500F54E418255"
SHOT_ID = "EP-001-SCN-001-SHT-002"
PLAN_ID = "H3SPANPLAN-EP-001-SCN-001-SHT-002-FBFFD471DCA2"
AUTHORITY_FINGERPRINT = "authority-fingerprint-phase-6-6b-5"


class _Probe:
    def __init__(self, *, frames: int = 144, fps: int = 24) -> None:
        self.frames = frames
        self.fps = fps

    def observe(self, path: Path) -> MiniMaxH3MediaObservation:
        return MiniMaxH3MediaObservation(
            frame_count=self.frames,
            frames_per_second=self.fps,
            width=1280,
            height=720,
        )


class _Inspector:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def inspect(self, media: object) -> TechnicalMediaObservation:
        relative_path = media.file.relative_path  # type: ignore[attr-defined]
        path = self.project_root / relative_path
        payload = path.read_bytes()
        return TechnicalMediaObservation(
            relative_path=relative_path,
            checksum_sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            container_format="mp4",
            video_codec="h264",
            width=1280,
            height=720,
            frame_rate=24.0,
            duration_seconds=6.0,
            has_video=True,
            has_audio=False,
        )


def _task(
    *,
    task_id: str = TASK_ID,
    shot_id: str = SHOT_ID,
    state: ProductionTaskState = ProductionTaskState.READY,
) -> ProductionTask:
    return ProductionTask(
        task_id=task_id,
        production_id="VSCS TSR2",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id=shot_id,
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{shot_id}",
            revision=1,
            fingerprint=AUTHORITY_FINGERPRINT,
            approved=True,
            approved_by="Neill Payne",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=state,
    )


def _write_evidence(
    project: Path,
    *,
    report_task_id: str = TASK_ID,
    report_shot_id: str = SHOT_ID,
    technical_passed: bool = True,
    visual_passed: bool = True,
    final_path: Path | None = None,
) -> Path:
    root = project / ".vscs" / "h3_span_orchestration" / TASK_ID / PLAN_ID
    root.mkdir(parents=True, exist_ok=True)
    media_path = final_path or (root / f"{SHOT_ID}-governed-h3-assembled.mp4")
    if final_path is None:
        media_path.write_bytes(b"accepted-h3-video")
    report = {
        "approved_by": "Neill Payne",
        "final_frame_count": 144,
        "final_path": str(media_path),
        "frames_per_second": 24,
        "notes": "Accepted functional-acceptance evidence.",
        "passed": technical_passed and visual_passed,
        "shot_id": report_shot_id,
        "state": "passed" if technical_passed and visual_passed else "failed",
        "task_id": report_task_id,
        "technical_failures": [] if technical_passed else ["technical"],
        "technical_passed": technical_passed,
        "visual_failures": [] if visual_passed else ["visual"],
        "visual_observation_present": True,
        "visual_passed": visual_passed,
    }
    (root / "functional_acceptance.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "report": report,
                "visual_observation": {"approved_by": "Neill Payne"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    manifest = {
        "provider": "minimax-h3-ref2va",
        "provider_profile_id": "minimax-h3-ref2va-v1",
        "provider_profile_fingerprint": "provider-profile-fingerprint",
        "execution_adapter_id": "minimax_h3_automated_execution",
        "shot_id": report_shot_id,
        "task_id": report_task_id,
        "source_package_fingerprint": "source-package-fingerprint",
        "plan_id": PLAN_ID,
        "plan_fingerprint": "plan-fingerprint",
        "final_path": str(media_path),
        "final_frame_count": 144,
        "frames_per_second": 24,
        "spans": [{}, {}],
    }
    (root / "orchestration.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return media_path


def _service(
    project: Path,
    *,
    task: ProductionTask | None = None,
    probe: _Probe | None = None,
) -> tuple[
    AcceptedProviderProductionReconciliationService,
    JsonProductionTaskRepository,
    GeneratedMediaPersistenceService,
    JsonGeneratedMediaSelectionRepository,
]:
    tasks = JsonProductionTaskRepository(project / "production" / "scheduling" / "tasks")
    current = task or _task()
    tasks.save(current)
    media = GeneratedMediaPersistenceService(
        JsonGeneratedMediaRepository(project / ".vscs" / "generated_media")
    )
    selections = JsonGeneratedMediaSelectionRepository(
        project / ".vscs" / "generated_media_selections"
    )
    adoption_store = ProviderProductionAdoptionStore(project)
    adoption_store.save_readiness(
        ProviderExecutionReadiness(
            task_id=current.task_id,
            shot_id=current.shot_id or "",
            execution_profile="production",
            provider_profile_id="minimax-h3-ref2va-v1",
            provider_profile_fingerprint="provider-profile-fingerprint",
            execution_adapter_id="minimax_h3_automated_execution",
            package_fingerprint="package-fingerprint",
            timed_span_state="qc_required",
            span_count=2,
            requirement_count=1,
            approved_keyframe_count=1,
            state=ProviderExecutionReadinessState.QC_REQUIRED,
        )
    )
    return (
        AcceptedProviderProductionReconciliationService(
            project,
            tasks,
            media,
            selections,
            adoption_store=adoption_store,
            media_probe=probe or _Probe(),
            technical_inspector=_Inspector(project),
        ),
        tasks,
        media,
        selections,
    )


def _finding_codes(
    service: AcceptedProviderProductionReconciliationService,
    task_id: str = TASK_ID,
) -> set[str]:
    return {finding.code for finding in service.assess(task_id).findings}


def test_reconcile_passed_h3_acceptance_creates_managed_approved_selected_media(
    tmp_path: Path,
) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project)
    service, _tasks, media, selections = _service(project)

    result = service.reconcile(TASK_ID)

    assert result.media.state.value == "approved"
    assert result.selection.selected_media_id == result.media.media_id
    assert result.adoption.state == "accepted"
    assert result.adoption.approved_by == "Neill Payne"
    assert (project / result.media.file.relative_path).is_file()
    attributes = dict(result.media.provenance.attributes)
    assert attributes["authority_fingerprint"] == AUTHORITY_FINGERPRINT
    assert attributes["provenance_source"] == "accepted-provider-functional-acceptance"
    assert attributes["reconciliation_phase"] == "20.18.2.3.6.6b.5"
    assert attributes["h3_plan_id"] == PLAN_ID
    assert dict(result.media.technical_metadata)["technical_validation.status"] == "passed"
    assert len(media.list_for_task(TASK_ID)) == 1
    assert len(selections.list_for_task(TASK_ID)) == 1


def test_reconciliation_is_idempotent_and_does_not_duplicate_media(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project)
    service, _tasks, media, selections = _service(project)

    first = service.reconcile(TASK_ID)
    second = service.reconcile(TASK_ID)

    assert not first.already_reconciled
    assert second.already_reconciled
    assert first.media.media_id == second.media.media_id
    assert len(media.list_for_task(TASK_ID)) == 1
    assert len(selections.list_for_task(TASK_ID)) == 1


def test_wrong_task_id_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project, report_task_id="PT-WRONG")
    service, *_ = _service(project)

    assert "functional-acceptance-not-passed" in _finding_codes(service)


def test_wrong_shot_id_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project, report_shot_id="EP-001-SCN-001-SHT-999")
    service, *_ = _service(project)

    assert "functional-acceptance-not-passed" in _finding_codes(service)


def test_missing_final_media_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    media_path = _write_evidence(project)
    media_path.unlink()
    service, *_ = _service(project)

    assert "accepted-media-missing" in _finding_codes(service)


def test_failed_technical_acceptance_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project, technical_passed=False)
    service, *_ = _service(project)

    assert "functional-acceptance-not-passed" in _finding_codes(service)


def test_failed_visual_acceptance_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project, visual_passed=False)
    service, *_ = _service(project)

    assert "functional-acceptance-not-passed" in _finding_codes(service)


def test_project_path_escape_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")
    _write_evidence(project, final_path=outside)
    service, *_ = _service(project)

    assert "accepted-media-path-escape" in _finding_codes(service)


def test_altered_frame_count_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project)
    service, *_ = _service(project, probe=_Probe(frames=143))

    assert "accepted-media-frame-count-mismatch" in _finding_codes(service)


def test_existing_authoritative_selection_is_not_silently_replaced(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project)
    service, _tasks, _media, selections = _service(project)
    selection = GeneratedMediaSelection(
        selection_id="GMS-EXISTING",
        production_id="VSCS TSR2",
        episode_id="EP-001",
        production_task_id=TASK_ID,
        kind=GeneratedMediaKind.VIDEO,
        selected_media_id="GM-EXISTING",
        selected_revision=1,
        selected_by="human:existing",
        reason="Existing authoritative production",
        selected_at=_task().created_at,
        history=(
            GeneratedMediaSelectionEvent(
                previous_media_id=None,
                selected_media_id="GM-EXISTING",
                selected_revision=1,
                actor="human:existing",
                reason="Existing authoritative production",
                occurred_at=_task().created_at,
            ),
        ),
    )
    selections.save(selection)

    assert "existing-authoritative-selection" in _finding_codes(service)


def test_current_task_authority_fingerprint_is_persisted_in_provenance(
    tmp_path: Path,
) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project)
    task = _task()
    service, *_ = _service(project, task=task)

    result = service.reconcile(TASK_ID)

    assert (
        dict(result.media.provenance.attributes)["authority_fingerprint"]
        == task.authority.fingerprint
    )


def test_non_current_task_state_is_not_eligible(tmp_path: Path) -> None:
    project = tmp_path / "Project"
    project.mkdir()
    _write_evidence(project)
    task = replace(_task(), state=ProductionTaskState.SUPERSEDED)
    service, *_ = _service(project, task=task)

    assert "task-state-not-reconcilable" in _finding_codes(service)
