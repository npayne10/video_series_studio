"""Guarded forwarding cannot treat Draft bindings or stale hashes as authority."""

import json

import pytest

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.governed_planning_evidence import verified_governed_shot_evidence


class ContractStub:
    def episode_contract_hash(self, episode: dict[str, object]) -> str:
        return "a" * 64

    def scene_contract_hash(self, scene: dict[str, object]) -> str:
        return "b" * 64

    def shot_contract_hash(self, shot: dict[str, object]) -> str:
        return "c" * 64


def test_draft_bindings_never_become_cap_evidence(tmp_path):
    root = tmp_path / "planning"
    root.mkdir()
    payloads = (
        (
            "episode_plans.json",
            "episodes",
            [{"episode_id": "EP-1", "story_id": "STORY-1", "status": "ready"}],
        ),
        (
            "scene_plans.json",
            "scenes",
            [
                {
                    "episode_id": "EP-1",
                    "scene_id": "SCN-1",
                    "status": "ready",
                    "episode_contract_hash": "a" * 64,
                }
            ],
        ),
        (
            "shot_plans.json",
            "shots",
            [
                {
                    "scene_id": "SCN-1",
                    "shot_id": "SHT-1",
                    "status": "ready",
                    "scene_contract_hash": "b" * 64,
                    "required_action": "Console in room",
                }
            ],
        ),
        (
            "asset_resolutions.json",
            "bindings",
            [
                {
                    "shot_id": "SHT-1",
                    "asset_id": "CAP-PRP-001",
                    "status": "draft",
                    "shot_contract_hash": "c" * 64,
                }
            ],
        ),
    )
    for name, key, rows in payloads:
        (root / name).write_text(json.dumps({key: rows}), encoding="utf-8")
    with pytest.raises(ShotTextAuthorityError, match="Draft or missing"):
        verified_governed_shot_evidence(tmp_path, "STORY-1", ContractStub())
