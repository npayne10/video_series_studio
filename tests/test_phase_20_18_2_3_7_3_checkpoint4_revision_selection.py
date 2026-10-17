"""Checkpoint 4 persisted assembly revision selection and fail-closed discovery."""

import pytest

from vscs.infrastructure.assembly_timeline import (
    AssemblyEvidenceError,
    JsonAssemblyTimelineRepository,
)
from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def test_empty_revision_discovery_remains_blocked(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.discover_revisions()
    assert workspace.persisted_revisions.count() == 1
    assert "No persisted timeline revisions" in workspace.status.text()
    assert not workspace.complete_button.isEnabled()


def test_malformed_persisted_revision_blocks_discovery(qtbot, tmp_path):
    folder = tmp_path / ".vscs" / "episode_assembly" / "revisions" / "ASM-1"
    folder.mkdir(parents=True)
    (folder / "REV-1.json").write_text("{}", encoding="utf-8")
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.discover_revisions()
    assert workspace.persisted_revisions.count() == 1
    assert "BLOCKED" in workspace.status.text()
    assert not workspace.complete_button.isEnabled()


def test_revision_repository_empty_and_malformed(tmp_path):
    repository = JsonAssemblyTimelineRepository(tmp_path)
    assert repository.list_revisions() == ()
    folder = repository.root / "ASM-1"
    folder.mkdir(parents=True)
    (folder / "REV-1.json").write_text("{}", encoding="utf-8")
    with pytest.raises(AssemblyEvidenceError):
        repository.list_revisions()
