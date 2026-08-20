from pathlib import Path

from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend


def test_nested_comfyui_output_setting_resolves_to_history_root(tmp_path: Path) -> None:
    output_root = tmp_path / "ComfyUI" / "output"
    nested = output_root / "Xorix" / "Production" / "production"
    nested.mkdir(parents=True)
    project = tmp_path / "project"
    project.mkdir()

    backend = LocalComfyUIProductionExecutionBackend(
        project,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=nested,
    )

    assert backend._require_comfyui_output_directory() == output_root


def test_comfyui_output_root_setting_is_preserved(tmp_path: Path) -> None:
    output_root = tmp_path / "ComfyUI" / "output"
    output_root.mkdir(parents=True)
    project = tmp_path / "project"
    project.mkdir()

    backend = LocalComfyUIProductionExecutionBackend(
        project,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=output_root,
    )

    assert backend._require_comfyui_output_directory() == output_root
