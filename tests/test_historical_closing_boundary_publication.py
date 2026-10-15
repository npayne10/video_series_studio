"""Fail-closed historical boundary publication contract."""

from types import SimpleNamespace

import pytest

from vscs.application.production_execution import ProductionExecutionError
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType
from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    LocalComfyUIProductionExecutionBackend,
)


def _backend(monkeypatch, task_state, media_items=()):
    backend = object.__new__(LocalComfyUIProductionExecutionBackend)
    task = SimpleNamespace(
        task_id="PT-OLD",
        shot_id="EP-001-SCN-001-SHT-002",
        state=task_state,
        task_type=ProductionTaskType.VIDEO_GENERATION,
    )
    monkeypatch.setattr(
        LocalComfyUIProductionExecutionBackend,
        "_require_task",
        lambda self, task_id: task,
    )
    backend.media = SimpleNamespace(list_for_task=lambda task_id: media_items)
    backend.execution_profiles = SimpleNamespace(
        profile_for_execution=lambda execution_id: "production"
    )
    return backend


def test_historical_publication_rejects_ready_task(monkeypatch):
    backend = _backend(monkeypatch, ProductionTaskState.READY)
    with pytest.raises(ProductionExecutionError, match="COMPLETED"):
        backend.historical_closing_boundary_eligibility("PT-OLD")


def test_historical_publication_rejects_nonproduction_profile(monkeypatch):
    backend = _backend(monkeypatch, ProductionTaskState.COMPLETED)
    with pytest.raises(ProductionExecutionError, match="production profile"):
        backend.historical_closing_boundary_eligibility("PT-OLD", profile="preview")


def test_historical_publication_rejects_missing_approved_video(monkeypatch):
    backend = _backend(monkeypatch, ProductionTaskState.COMPLETED)
    with pytest.raises(ProductionExecutionError, match="exactly one APPROVED"):
        backend.historical_closing_boundary_eligibility("PT-OLD")


def test_historical_publication_rejects_ambiguous_approved_videos(monkeypatch):
    from vscs.domain.generated_media import GeneratedMediaKind, GeneratedMediaState

    media = SimpleNamespace(
        media_id="GM-TEST",
        kind=GeneratedMediaKind.VIDEO,
        state=GeneratedMediaState.APPROVED,
        scope=SimpleNamespace(shot_id="EP-001-SCN-001-SHT-002"),
        provenance=SimpleNamespace(execution_id="EXEC-1"),
    )
    backend = _backend(monkeypatch, ProductionTaskState.COMPLETED, (media, media))
    with pytest.raises(ProductionExecutionError, match="found 2"):
        backend.historical_closing_boundary_eligibility("PT-OLD")
