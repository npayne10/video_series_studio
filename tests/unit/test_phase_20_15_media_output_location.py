from pathlib import Path

import pytest
from pydantic import ValidationError

from vscs.application.generated_media import GeneratedMediaIngestionError
from vscs.infrastructure.configuration.models import WorkspaceSettings
from vscs.infrastructure.generated_media import (
    LocalGeneratedMediaFileStore,
    ProjectMediaOutputError,
    ProjectMediaOutputResolver,
)


def test_media_output_defaults_to_standard_project_folder(tmp_path: Path) -> None:
    settings = WorkspaceSettings()

    assert settings.media_output_directory == "Media Output"
    assert ProjectMediaOutputResolver.relative_path(tmp_path) == "Media Output"
    assert ProjectMediaOutputResolver.resolve(tmp_path) == (tmp_path / "Media Output").resolve()


def test_configured_media_output_remains_project_relative(tmp_path: Path) -> None:
    settings = WorkspaceSettings(media_output_directory=r"Production\Final Media")

    assert settings.media_output_directory == "Production/Final Media"
    assert ProjectMediaOutputResolver.relative_path(
        tmp_path, settings.media_output_directory
    ) == "Production/Final Media"


@pytest.mark.parametrize(
    "unsafe",
    (
        "../outside",
        "Media Output/../../outside",
        "/absolute/output",
        r"C:\outside\output",
        ".",
    ),
)
def test_workspace_settings_reject_media_output_escape(unsafe: str) -> None:
    with pytest.raises(ValidationError):
        WorkspaceSettings(media_output_directory=unsafe)


def test_output_resolver_rejects_media_output_escape(tmp_path: Path) -> None:
    with pytest.raises(ProjectMediaOutputError):
        ProjectMediaOutputResolver.resolve(tmp_path, "../outside")


def test_generated_media_file_store_prefixes_configured_media_root(tmp_path: Path) -> None:
    source_root = tmp_path / "comfyui-output"
    project_root = tmp_path / "project"
    source_root.mkdir()
    project_root.mkdir()
    source = source_root / "Xorix" / "clip.mp4"
    source.parent.mkdir()
    source.write_bytes(b"phase-20.15-media")

    store = LocalGeneratedMediaFileStore(
        source_root,
        project_root,
        managed_relative_root="Media Output",
    )
    managed = store.ingest(
        "Xorix/clip.mp4",
        "generated_media/XORIX/EP-001/PT-001/GM-001.mp4",
    )

    assert managed.relative_path == (
        "Media Output/generated_media/XORIX/EP-001/PT-001/GM-001.mp4"
    )
    assert (project_root / Path(managed.relative_path)).read_bytes() == b"phase-20.15-media"
    assert source.exists()
    assert source.read_bytes() == b"phase-20.15-media"


def test_generated_media_file_store_rejects_unsafe_managed_root(tmp_path: Path) -> None:
    with pytest.raises(GeneratedMediaIngestionError, match="managed media root"):
        LocalGeneratedMediaFileStore(
            tmp_path / "source",
            tmp_path / "project",
            managed_relative_root="../outside",
        )
