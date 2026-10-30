"""Discovery uses existing planning files without claiming unverified hash authority."""

import json

from vscs.application.caps.governed_planning_evidence import discover_governed_shot_evidence


def _write(root, name, key, items):
    folder = root / "planning"
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(json.dumps({"schema_version": "1.0", key: items}), encoding="utf-8")


def test_governed_chain_reuses_persisted_records_and_does_not_write(tmp_path):
    hash_value = "a" * 64
    _write(
        tmp_path,
        "episode_plans.json",
        "episodes",
        [{"story_id": "STORY-001", "episode_id": "EP-001", "status": "ready"}],
    )
    _write(
        tmp_path,
        "scene_plans.json",
        "scenes",
        [
            {
                "episode_id": "EP-001",
                "scene_id": "SCN-001",
                "status": "ready",
                "episode_contract_hash": hash_value,
            }
        ],
    )
    _write(
        tmp_path,
        "shot_plans.json",
        "shots",
        [
            {
                "scene_id": "SCN-001",
                "shot_id": "SHT-001",
                "status": "ready",
                "scene_contract_hash": hash_value,
                "required_action": "Diagnostic Console inside Engineering Control Room.",
            }
        ],
    )
    _write(
        tmp_path,
        "asset_resolutions.json",
        "bindings",
        [
            {
                "shot_id": "SHT-001",
                "asset_id": "CAP-PRP-001",
                "status": "draft",
                "shot_contract_hash": hash_value,
            }
        ],
    )
    result = discover_governed_shot_evidence(tmp_path, "STORY-001")
    assert len(result.candidates) == 1
    assert result.candidates[0].text_fields[0][0] == "required_action"
    assert result.candidates[0].binding_statuses == ("draft",)
    assert result.hashes_verified is False
    assert "discovery-only" in result.warnings[-1]
    assert not (tmp_path / "story").exists()


def test_other_story_is_not_included(tmp_path):
    for filename, key in (
        ("episode_plans.json", "episodes"),
        ("scene_plans.json", "scenes"),
        ("shot_plans.json", "shots"),
        ("asset_resolutions.json", "bindings"),
    ):
        items = (
            [{"story_id": "STORY-OTHER", "episode_id": "EP-001", "status": "ready"}]
            if key == "episodes"
            else []
        )
        _write(tmp_path, filename, key, items)
    result = discover_governed_shot_evidence(tmp_path, "STORY-001")
    assert not result.candidates
