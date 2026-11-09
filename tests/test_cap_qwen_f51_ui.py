"""F5.1 CAP dialog tests: inspection never submits or reserves GPU attempts."""

from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QMessageBox

from vscs.presentation.widgets import cap_visual_candidate_regeneration as ui


def _dialog(qtbot, monkeypatch, tmp_path):
    plan = SimpleNamespace(
        source=SimpleNamespace(
            asset_id="STORY-LOC-TEST",
            reference_id=2,
            project_root=tmp_path,
        ),
        correction_rules=("Exactly one door",),
        review_findings=("Extra doors visible",),
        effectiveness_warnings=(),
        request=SimpleNamespace(prompt="Reviewed correction only"),
        attempt=2,
        max_attempts=2,
    )
    service = SimpleNamespace(
        prepare=Mock(return_value=plan),
        verify_current=Mock(),
        generator=SimpleNamespace(render=Mock(), persist_candidate=Mock()),
    )
    monkeypatch.setattr(ui, "CandidateRegenerationService", lambda _references: service)
    dialog = ui.ControlledCandidateRegenerationDialog(
        SimpleNamespace(), plan.source.asset_id, plan.source.reference_id, tmp_path / "report.json"
    )
    qtbot.addWidget(dialog)
    return dialog, service


def _run_read_only(_runner, _title, _asset, callback, *, may_charge=True):
    assert may_charge is False
    return callback()


def _ready_report():
    return SimpleNamespace(
        status="PREFLIGHT_READY_NO_GPU_INFERENCE",
        graph_sha256="reviewed-workflow-sha",
        endpoint="http://127.0.0.1:8188",
        comfyui_reachable=True,
        nodes_and_models_available=True,
        gpu_inventory=(
            {
                "name": "RTX 5060 Ti",
                "memory_free_mib": "14126",
                "memory_total_mib": "16311",
                "driver_version": "616.64",
            },
        ),
        errors=(),
    )


def test_f51_dual_workflow_inspection_is_read_only(qtbot, tmp_path, monkeypatch):
    dialog, service = _dialog(qtbot, monkeypatch, tmp_path)
    inspection = Mock()
    inspection.describe.return_value = "LEGACY XCIC\nMANAGED QWEN\nNO GPU"
    monkeypatch.setattr(ui, "inspect_dual_workflows", Mock(return_value=inspection))
    monkeypatch.setattr(ui.XCICConfiguration, "load", lambda: SimpleNamespace())
    notice = Mock()
    monkeypatch.setattr(QMessageBox, "information", notice)
    dialog.inspect_spatial_button.click()
    assert notice.call_count == 1
    assert "MANAGED QWEN" in notice.call_args.args[2]
    assert "Both Workflows" in dialog.inspect_spatial_button.text()
    service.verify_current.assert_not_called()
    service.generator.render.assert_not_called()
    service.generator.persist_candidate.assert_not_called()
    assert dialog._f5_preflight_sha256 is None


def test_f51_preflight_ready_does_not_submit_or_reserve(qtbot, tmp_path, monkeypatch):
    dialog, service = _dialog(qtbot, monkeypatch, tmp_path)
    monkeypatch.setattr(
        ui.XCICConfiguration,
        "load",
        lambda: SimpleNamespace(comfyui_url="http://127.0.0.1:8188"),
    )
    read_only = Mock(return_value=_ready_report())
    monkeypatch.setattr(ui, "inspect_qwen_f5_hardware", read_only)
    monkeypatch.setattr(ui.AutomationProgressRunner, "run", _run_read_only)
    notice = Mock()
    monkeypatch.setattr(QMessageBox, "information", notice)
    dialog.f5_preflight_button.click()
    assert dialog._f5_preflight_sha256 == "reviewed-workflow-sha"
    assert "PREFLIGHT READY" in dialog.f5_status_label.text()
    read_only.assert_called_once_with(comfyui_url="http://127.0.0.1:8188")
    assert "no image generated" in notice.call_args.args[2]
    service.verify_current.assert_not_called()
    service.generator.render.assert_not_called()
    service.generator.persist_candidate.assert_not_called()


def test_f51_qwen_generation_blocked_before_preflight(qtbot, tmp_path, monkeypatch):
    dialog, service = _dialog(qtbot, monkeypatch, tmp_path)
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    submit = Mock()
    monkeypatch.setattr(ui, "execute_prepared_managed_qwen_edit", submit)
    dialog.guided_edit_button.click()
    warning.assert_called_once()
    submit.assert_not_called()
    service.verify_current.assert_not_called()
    service.generator.persist_candidate.assert_not_called()


def test_f51_failed_preflight_disables_qwen_execution(qtbot, tmp_path, monkeypatch):
    dialog, service = _dialog(qtbot, monkeypatch, tmp_path)
    monkeypatch.setattr(
        ui.XCICConfiguration,
        "load",
        lambda: SimpleNamespace(comfyui_url="http://127.0.0.1:8188"),
    )
    failed = SimpleNamespace(
        status="BLOCKED",
        graph_sha256="",
        endpoint="http://127.0.0.1:8188",
        comfyui_reachable=True,
        nodes_and_models_available=False,
        gpu_inventory=(),
        errors=("Missing Qwen model",),
    )
    monkeypatch.setattr(ui, "inspect_qwen_f5_hardware", lambda **_kw: failed)
    monkeypatch.setattr(ui.AutomationProgressRunner, "run", _run_read_only)
    monkeypatch.setattr(QMessageBox, "information", Mock())
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    dialog.f5_preflight_button.click()
    assert dialog._f5_preflight_sha256 is None
    assert "BLOCKED" in dialog.f5_status_label.text()
    dialog.guided_edit_button.click()
    warning.assert_called_once()
    service.generator.render.assert_not_called()


def test_f51_stale_workflow_invalidates_prior_hardware_readiness(qtbot, tmp_path, monkeypatch):
    dialog, service = _dialog(qtbot, monkeypatch, tmp_path)
    dialog._f5_preflight_sha256 = "old-workflow"
    dialog._f5_preflight_endpoint = "http://127.0.0.1:8188"
    dialog.f5_final_attempt_ack.setChecked(True)
    contract = SimpleNamespace(workflow_sha256="new-workflow")
    monkeypatch.setattr(ui, "prepare_spatial_contract", Mock(return_value=contract))
    monkeypatch.setattr(
        ui, "inspect_managed_qwen_edit_workflow",
        Mock(return_value=SimpleNamespace(workflow_sha256="new-workflow")),
    )
    critical = Mock()
    consent = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)
    monkeypatch.setattr(QMessageBox, "question", consent)
    dialog._generate_guided_edit()
    assert dialog._f5_preflight_sha256 is None
    critical.assert_called_once()
    consent.assert_not_called()
    service.generator.render.assert_not_called()


def test_f51_final_attempt_needs_separate_acknowledgement(qtbot, tmp_path, monkeypatch):
    dialog, service = _dialog(qtbot, monkeypatch, tmp_path)
    dialog._f5_preflight_sha256 = "reviewed-workflow-sha"
    dialog._f5_preflight_endpoint = "http://127.0.0.1:8188"
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    consent = Mock()
    monkeypatch.setattr(QMessageBox, "question", consent)
    assert not dialog.f5_final_attempt_ack.isChecked()
    dialog._generate_guided_edit()
    warning.assert_called_once()
    consent.assert_not_called()
    service.generator.render.assert_not_called()
    service.generator.persist_candidate.assert_not_called()
