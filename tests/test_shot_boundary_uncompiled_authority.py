"""Regression: uncompiled boundary status uses pinned READY UPD authority."""

from types import SimpleNamespace

from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    LocalComfyUIProductionExecutionBackend,
)


def _backend(tmp_path, monkeypatch, mode):
    backend = object.__new__(LocalComfyUIProductionExecutionBackend)
    backend.project_directory = tmp_path
    task = SimpleNamespace(task_id="PT-TEST", shot_id="EP-001-SCN-001-SHT-003")
    monkeypatch.setattr(
        LocalComfyUIProductionExecutionBackend,
        "_require_task",
        lambda self, task_id: task,
    )
    continuity = {
        "shot_boundary_mode": mode,
        "source_shot_id": "EP-001-SCN-001-SHT-002",
    }
    backend.package_compilation = SimpleNamespace(
        status=lambda task, profile: SimpleNamespace(path=None),
        _authority_source=lambda task: SimpleNamespace(
            universal_description={"production": {"continuity": continuity}}
        ),
    )
    return backend


def test_uncompiled_continuous_shot_shows_governed_mode_and_missing_boundary(
    tmp_path, monkeypatch
):
    backend = _backend(tmp_path, monkeypatch, "continuous")

    status = backend.shot_boundary_status_for_profile("PT-TEST", profile="production")

    assert status.opening_mode.value == "continuous"
    assert status.opening_source_shot_id == "EP-001-SCN-001-SHT-002"
    assert status.opening_state == "stale"
    assert "No governed closing boundary frame" in status.message


def test_uncompiled_new_composition_does_not_require_previous_closing_frame(
    tmp_path, monkeypatch
):
    backend = _backend(tmp_path, monkeypatch, "new_composition")

    status = backend.shot_boundary_status_for_profile("PT-TEST", profile="production")

    assert status.opening_mode.value == "new_composition"
    assert status.opening_source_shot_id is None
    assert status.opening_state == "independent"
    assert "No governed closing boundary frame" not in status.message
