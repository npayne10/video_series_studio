"""Tests for optional OpenAI Shot asset requirement inference."""

from __future__ import annotations

from types import SimpleNamespace

from vscs.application.story import (
    CinematicCoverageRole,
    ShotAssetInferenceSource,
    ShotPlan,
)
from vscs.infrastructure.ai.shot_asset_provider import OpenAIShotAssetRequirementProvider


class _Responses:
    def parse(self, **_kwargs):
        return SimpleNamespace(
            output_parsed={
                "requirements": [
                    {
                        "role": "Information-bearing Shot element",
                        "requirement": "Signal display is required to show the repeating pattern.",
                        "expected_category": "technology",
                        "confidence": 0.84,
                        "rationale": "The Detail Insert requires a visible signal display.",
                    }
                ]
            }
        )


class _Client:
    responses = _Responses()


def test_openai_shot_asset_provider_returns_proposals_without_creating_canon() -> None:
    provider = OpenAIShotAssetRequirementProvider.__new__(
        OpenAIShotAssetRequirementProvider
    )
    provider._client = _Client()
    provider.model_name = "test-model"

    shot = ShotPlan(
        shot_id="EP-001-SCN-001-SHT-003",
        scene_id="EP-001-SCN-001",
        sequence_number=3,
        title="Weak Repeating Transmission — Detail",
        narrative_purpose="Reveal an information-bearing detail.",
        production_objective="Show the signal pattern.",
        target_runtime_seconds=7,
        required_action="Show the repeating forty-seven second pattern on the display.",
        coverage_role=CinematicCoverageRole.DETAIL_INSERT,
        scene_contract_hash="scene",
    )

    proposals = provider.infer_requirements(
        shot=shot,
        scene_text="Sandra studies the weak repeating signal on the bridge display.",
        deterministic=(),
    )

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.source is ShotAssetInferenceSource.AI_SEMANTIC
    assert proposal.expected_category.value == "technology"
    assert proposal.matched_asset_id == ""
    assert proposal.canonical_status == "unresolved"
    assert proposal.confidence == 0.84
