"""Isolated operator H3 readiness button: never submit a provider job."""

from types import SimpleNamespace

from vscs.presentation.widgets import production_task_readiness_workspace as ui


def _operator():
    class Workspace:
        def _refresh_production_tasks(self):
            return None

        def _compile_production_tasks(self):
            return None

        def _production_task_context(self):
            return None

        def _production_task_blocker(self):
            return ""

    # Install the callback on the type without running the Qt-heavy wrapped
    # __init__: this isolated test exercises the operator action, not UI layout.
    ui.install_production_task_readiness_workspace(Workspace)
    workspace = object.__new__(Workspace)
    status = SimpleNamespace(value="", setText=lambda text: setattr(status, "value", text))
    workspace.production_task_readiness_status = status
    workspace._selected_persisted_production_task = lambda: SimpleNamespace(
        task_id="PT-ISOLATED",
        shot_id="SHT-ISOLATED",
        task_type=SimpleNamespace(value="video_generation"),
    )
    workspace.projects = SimpleNamespace(project_directory="ISOLATED")
    workspace.packages = SimpleNamespace(planning=object())
    return workspace, status


def test_operator_h3_preflight_blocks_missing_configuration(monkeypatch):
    workspace, status = _operator()
    for name in (
        "VSCS_H3_COMFYUI_ENDPOINT",
        "VSCS_H3_COMFYUI_INPUT_DIR",
        "VSCS_H3_COMFYUI_OUTPUT_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        ui.MiniMaxH3AutomatedExecutionService,
        "from_project_services",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("No H3 service may be constructed without configuration")
        ),
    )
    workspace._verify_h3_operator_readiness()
    assert "BLOCKED" in status.value
    assert "No provider request was sent" in status.value


def test_operator_h3_preflight_ready_never_executes(monkeypatch, tmp_path):
    workspace, status = _operator()
    monkeypatch.setenv("VSCS_H3_COMFYUI_ENDPOINT", "http://127.0.0.1:8188")
    monkeypatch.setenv("VSCS_H3_COMFYUI_INPUT_DIR", str(tmp_path))
    monkeypatch.setenv("VSCS_H3_COMFYUI_OUTPUT_DIR", str(tmp_path))
    calls = []

    class Service:
        def preflight(self, task_id):
            calls.append(("preflight", task_id))
            return SimpleNamespace(span_count=2, provider_profile_id="minimax-h3-ref2va-v1")

        def execute(self, *args, **kwargs):
            raise AssertionError("Read-only operator action must never execute H3")

    def construct(projects, planning, **kwargs):
        assert projects is workspace.projects
        assert planning is workspace.packages.planning
        calls.append(("factory", kwargs["endpoint"]))
        return Service()

    monkeypatch.setattr(
        ui.MiniMaxH3AutomatedExecutionService,
        "from_project_services",
        construct,
    )
    workspace._verify_h3_operator_readiness()
    assert calls == [
        ("factory", "http://127.0.0.1:8188"),
        ("preflight", "PT-ISOLATED"),
    ]
    assert "READY" in status.value
    assert "no provider job submitted" in status.value
