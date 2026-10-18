"""Checkpoint 4B.4: only existing governed declaration evidence supplies scope."""

import json

import pytest

from vscs.application.episode_assembly_scope import verified_episode_assembly_scope


def test_missing_governed_scope_never_fabricated(tmp_path):
    assert verified_episode_assembly_scope(tmp_path, "EP-001") is None


def test_malformed_governed_scope_fails_closed(tmp_path):
    root = tmp_path / ".vscs" / "episode_assembly" / "shot_set_declarations"
    root.mkdir(parents=True)
    (root / "DECL-1.json").write_text(json.dumps({"scope": {}}), encoding="utf-8")
    with pytest.raises((KeyError, ValueError, TypeError)):
        verified_episode_assembly_scope(tmp_path, "EP-001")


def test_missing_project_never_supplies_scope():
    assert verified_episode_assembly_scope(None, "EP-001") is None
