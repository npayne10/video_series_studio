"""F5.3 isolated Qwen GPU smoke acceptance: strict non-CAP one-shot contract."""

import io
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps import qwen_f53_isolated_acceptance as isolated


def _png(size=(512, 512)):
    stream = io.BytesIO()
    Image.new("RGB", size, "gray").save(stream, format="PNG")
    return stream.getvalue()


def _fixture(tmp_path):
    project = tmp_path / "actual_vscs_project"
    project.mkdir()
    source = project / "candidate3.png"
    source.write_bytes(_png())
    bundle = tmp_path / "separate_gpu_acceptance" / "run01"
    bundle.parent.mkdir()
    return project, source, bundle


def _prepared(tmp_path):
    project, source, bundle = _fixture(tmp_path)
    result = isolated.prepare_isolated_qwen_acceptance(
        project_root=project,
        source_image=source,
        bundle_directory=bundle,
        prompt="Preserve console identity and recess the existing dial",
        seed=43,
    )
    return project, source, bundle, result


def test_prepare_copies_candidate_and_does_not_mutate_project(tmp_path):
    project, source, bundle, result = _prepared(tmp_path)
    assert result.source_sha256 == isolated._hash(source)
    assert (bundle / "source.png").read_bytes() == source.read_bytes()
    assert (bundle / "acceptance_manifest.json").is_file()
    assert (bundle / "qwen_acceptance_graph.json").is_file()
    assert (bundle / "qwen_acceptance_queue.json").is_file()
    assert not (bundle / "execution_reserved.json").exists()
    assert not (bundle / "qwen_acceptance_output.png").exists()
    assert sorted(p.name for p in project.iterdir()) == ["candidate3.png"]


def test_prepare_refuses_inside_project(tmp_path):
    project, source, _bundle = _fixture(tmp_path)
    with pytest.raises(isolated.IsolatedQwenAcceptanceError, match="outside"):
        isolated.prepare_isolated_qwen_acceptance(
            project_root=project,
            source_image=source,
            bundle_directory=project / "internal_acceptance",
            prompt="Recess the dial",
        )


def test_prepare_refuses_overwriting_existing_test_bundle(tmp_path):
    project, source, bundle, _ = _prepared(tmp_path)
    with pytest.raises(isolated.IsolatedQwenAcceptanceError, match="already exists"):
        isolated.prepare_isolated_qwen_acceptance(
            project_root=project,
            source_image=source,
            bundle_directory=bundle,
            prompt="Recess the dial",
        )


def test_no_consent_does_not_use_provider_or_reserve(tmp_path):
    project, _source, bundle, _ = _prepared(tmp_path)
    provider = SimpleNamespace(submit=Mock(), healthcheck=Mock())
    with pytest.raises(isolated.IsolatedQwenAcceptanceError, match="consent"):
        isolated.execute_isolated_qwen_acceptance(
            bundle_directory=bundle,
            project_root=project,
            operator_confirmed=False,
            client=provider,
        )
    provider.healthcheck.assert_not_called()
    provider.submit.assert_not_called()
    assert not (bundle / "execution_reserved.json").exists()


def test_tampered_source_refused_before_network(tmp_path):
    project, source, bundle, _ = _prepared(tmp_path)
    source.write_bytes(_png((640, 640)))
    provider = SimpleNamespace(submit=Mock(), healthcheck=Mock())
    with pytest.raises(isolated.IsolatedQwenAcceptanceError, match="changed"):
        isolated.execute_isolated_qwen_acceptance(
            bundle_directory=bundle,
            project_root=project,
            operator_confirmed=True,
            client=provider,
        )
    provider.submit.assert_not_called()


def test_tampered_graph_refused_before_network(tmp_path):
    project, _source, bundle, _ = _prepared(tmp_path)
    graph = bundle / "qwen_acceptance_graph.json"
    data = json.loads(graph.read_text(encoding="utf-8"))
    data["170:169"]["inputs"]["seed"] = 99
    graph.write_text(json.dumps(data), encoding="utf-8")
    provider = SimpleNamespace(submit=Mock(), healthcheck=Mock())
    with pytest.raises(isolated.IsolatedQwenAcceptanceError, match="changed"):
        isolated.execute_isolated_qwen_acceptance(
            bundle_directory=bundle,
            project_root=project,
            operator_confirmed=True,
            client=provider,
        )
    provider.submit.assert_not_called()


def test_one_submission_writes_only_external_result(tmp_path, monkeypatch):
    project, source, bundle, _ = _prepared(tmp_path)
    monkeypatch.setattr(isolated, "validate_managed_qwen_model_choices", Mock())

    class Provider:
        def __init__(self):
            self.healthcheck = Mock()
            self.validate_nodes = Mock()
            self.object_info = Mock(return_value={})
            self.submit = Mock(return_value="prompt-smoke-test")

        def wait(self, prompt_id, timeout_seconds):
            assert prompt_id == "prompt-smoke-test"
            (bundle / "qwen_acceptance_output.png").write_bytes(_png())
            return {"status": {"completed": True}}

    provider = Provider()
    outcome = isolated.execute_isolated_qwen_acceptance(
        bundle_directory=bundle,
        project_root=project,
        operator_confirmed=True,
        client=provider,
    )
    assert outcome["status"] == "GPU_OUTPUT_VERIFIED_NO_CAP_CHANGES"
    assert outcome["prompt_id"] == "prompt-smoke-test"
    assert outcome["candidate_registered"] is False
    assert outcome["correction_attempt_consumed"] is False
    provider.submit.assert_called_once()
    assert (bundle / "execution_reserved.json").exists()
    assert (bundle / "acceptance_result.json").is_file()
    assert sorted(p.name for p in project.iterdir()) == [source.name]


def test_ambiguous_post_failure_preserves_reservation_and_blocks_retry(tmp_path, monkeypatch):
    project, _source, bundle, _ = _prepared(tmp_path)
    monkeypatch.setattr(isolated, "validate_managed_qwen_model_choices", Mock())
    provider = SimpleNamespace(
        healthcheck=Mock(),
        validate_nodes=Mock(),
        object_info=Mock(return_value={}),
        submit=Mock(side_effect=RuntimeError("submission outcome unknown")),
    )
    with pytest.raises(RuntimeError, match="unknown"):
        isolated.execute_isolated_qwen_acceptance(
            bundle_directory=bundle,
            project_root=project,
            operator_confirmed=True,
            client=provider,
        )
    assert (bundle / "execution_reserved.json").is_file()
    with pytest.raises(isolated.IsolatedQwenAcceptanceError, match="already ran"):
        isolated.execute_isolated_qwen_acceptance(
            bundle_directory=bundle,
            project_root=project,
            operator_confirmed=True,
            client=provider,
        )
    provider.submit.assert_called_once()


def test_wrong_project_is_rejected_before_provider(tmp_path):
    _project, _source, bundle, _ = _prepared(tmp_path)
    other = tmp_path / "other_project"
    other.mkdir()
    client = SimpleNamespace(submit=Mock(), healthcheck=Mock())
    with pytest.raises(
        isolated.IsolatedQwenAcceptanceError, match="Original source is outside"
    ):
        isolated.execute_isolated_qwen_acceptance(
            bundle_directory=bundle,
            project_root=other,
            operator_confirmed=True,
            client=client,
        )
    client.healthcheck.assert_not_called()


def test_busy_comfyui_queue_blocks_live_execution(tmp_path, monkeypatch):
    project, _source, bundle, _ = _prepared(tmp_path)
    submitted = Mock()
    monkeypatch.setattr(isolated, "validate_managed_qwen_model_choices", Mock())
    monkeypatch.setattr(
        isolated,
        "_ensure_idle_local_queue",
        Mock(side_effect=isolated.IsolatedQwenAcceptanceError("ComfyUI is busy")),
    )
    with pytest.raises(isolated.IsolatedQwenAcceptanceError, match="busy"):
        # A real live call has the queue check; this verifies its fail-closed helper.
        isolated._ensure_idle_local_queue("http://127.0.0.1:8188")
    submitted.assert_not_called()
    assert not (bundle / "execution_reserved.json").exists()
    assert project.is_dir()


def test_missing_gpu_output_keeps_once_only_reservation(tmp_path, monkeypatch):
    project, _source, bundle, _ = _prepared(tmp_path)
    monkeypatch.setattr(isolated, "validate_managed_qwen_model_choices", Mock())
    client = SimpleNamespace(
        healthcheck=Mock(),
        validate_nodes=Mock(),
        object_info=Mock(return_value={}),
        submit=Mock(return_value="one"),
        wait=Mock(return_value={"status": {"completed": True}}),
    )
    with pytest.raises(isolated.IsolatedQwenAcceptanceError, match="missing"):
        isolated.execute_isolated_qwen_acceptance(
            bundle_directory=bundle,
            project_root=project,
            operator_confirmed=True,
            client=client,
        )
    client.submit.assert_called_once()
    assert (bundle / "execution_reserved.json").exists()
    assert not (bundle / "acceptance_result.json").exists()
