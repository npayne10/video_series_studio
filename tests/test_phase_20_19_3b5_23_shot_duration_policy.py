"""B.5.23: provider Shot proposals must respect 15–20s without replaying events."""

from types import SimpleNamespace

import pytest

from vscs.application.automation.contracts import (
    AutomationProposal,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from vscs.application.automation.scene_shot import (
    SceneShotProposalAutomationService,
    SceneShotProposalDraft,
    ShotProposalDraft,
)


def _scene(seconds):
    return AutomationProposal(
        proposal_id="AUT-SCENE-TEST",
        proposal_type=AutomationProposalType.SCENE,
        target_id="EP-001-SCN-001",
        payload={"target_runtime_seconds": seconds},
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.AI_INFERENCE,
            source_story_id="STORY-001",
            source_revision="source-revision",
            source_scope="disposable scene",
            provider="test",
            model="test",
        ),
        status=AutomationProposalStatus.ACCEPTED,
        accepted_by="VSCS Acceptance Test",
    )


def _shot(seconds, sequence=1):
    return ShotProposalDraft(
        sequence_number=sequence,
        title="Diagnostic console watch",
        narrative_purpose="Observe the single indicator pulse",
        production_objective="Keep camera stationary",
        target_runtime_seconds=seconds,
        required_action="Indicator pulses exactly once, then returns to steady glow.",
        continuity_in="Steady blue glow",
        continuity_out="Steady blue glow restored",
        shot_constraints=("No personnel", "Keep camera static"),
        confidence=0.9,
    )


def _transform(seconds):
    service = SceneShotProposalAutomationService
    return service._enforce_shot_duration_policy(
        _scene(seconds), SceneShotProposalDraft(shots=(_shot(seconds),))
    )


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (15, (15,)),
        (20, (20,)),
        (35, (18, 17)),
        (40, (20, 20)),
        (45, (15, 15, 15)),
    ],
)
def test_duration_is_partitioned_without_losing_scene_budget(seconds, expected):
    result = _transform(seconds)
    assert tuple(shot.target_runtime_seconds for shot in result.shots) == expected
    assert tuple(shot.sequence_number for shot in result.shots) == tuple(
        range(1, len(expected) + 1)
    )
    assert sum(shot.target_runtime_seconds for shot in result.shots) == seconds


def test_one_time_indicator_pulse_is_assigned_to_one_shot_only():
    shots = _transform(35).shots
    assert "pulses exactly once" in shots[0].required_action
    assert "pulses exactly once" not in shots[1].required_action
    assert "do not repeat" in shots[1].required_action
    assert shots[0].continuity_in == "Steady blue glow"
    assert shots[-1].continuity_out == "Steady blue glow restored"
    assert shots[0].shot_constraints == ("No personnel", "Keep camera static")
    assert "No personnel" in shots[1].shot_constraints
    assert "Do not replay" in shots[1].shot_constraints[-1]


@pytest.mark.parametrize("seconds", [1, 14, 21, 22, 29, 41, 44])
def test_impossible_duration_is_rejected_not_silently_approved(seconds):
    with pytest.raises(ValueError, match=r"minimum|Cannot split"):
        _transform(seconds)


def test_shorter_provider_output_does_not_silently_trim_scene_budget():
    scene = _scene(35)
    service = SceneShotProposalAutomationService
    with pytest.raises(ValueError, match="requires 35s"):
        service._enforce_shot_duration_policy(
            scene, SceneShotProposalDraft(shots=(_shot(17),))
        )


def test_complete_service_creates_two_unapproved_shots_not_governed_authority():
    scene = _scene(35)

    class Store:
        def __init__(self):
            self.saved = []

        def list_proposals(self):
            return (scene,)

        def save(self, proposal):
            self.saved.append(proposal)
            return proposal

    class Provider:
        provider_name = "test-openai"
        model_name = "test-model"

        def propose_scene_shots(self, **_kwargs):
            return SceneShotProposalDraft(shots=(_shot(35),))

    store = Store()
    service = SceneShotProposalAutomationService(Provider(), store)
    result = service.generate(
        story_id="STORY-001",
        source_text="The empty engineering room holds one indicator pulse.",
        source_revision="source-revision",
        baseline=SimpleNamespace(story_id="STORY-001", source_revision="source-revision"),
    )
    assert len(result) == 2
    assert tuple(item.target_id for item in result) == (
        "EP-001-SCN-001-SHT-001",
        "EP-001-SCN-001-SHT-002",
    )
    assert all(item.status is AutomationProposalStatus.PROPOSED for item in result)
    assert len(store.saved) == 2
    assert sum(item.payload["target_runtime_seconds"] for item in result) == 35
    assert result[0].metadata["parent_scene_proposal_id"] == scene.proposal_id


def test_invalid_generated_shot_is_not_saved_to_proposal_repository():
    scene = _scene(22)

    class Store:
        def __init__(self):
            self.saved = []

        def list_proposals(self):
            return (scene,)

        def save(self, proposal):
            self.saved.append(proposal)
            return proposal

    class Provider:
        provider_name = "test-openai"
        model_name = "test-model"

        def propose_scene_shots(self, **_kwargs):
            return SceneShotProposalDraft(shots=(_shot(22),))

    store = Store()
    service = SceneShotProposalAutomationService(Provider(), store)
    with pytest.raises(ValueError, match="Cannot split"):
        service.generate(
            story_id="STORY-001",
            source_text="A short scene.",
            source_revision="source-revision",
            baseline=SimpleNamespace(story_id="STORY-001", source_revision="source-revision"),
        )
    assert store.saved == []


def test_accepted_shot_is_never_overwritten_by_regeneration():
    scene = _scene(35)
    prior = AutomationProposal(
        proposal_id="AUT-SHOT-ACCEPTED",
        proposal_type=AutomationProposalType.SHOT,
        target_id="EP-001-SCN-001-SHT-001",
        payload={"target_runtime_seconds": 35},
        provenance=scene.provenance,
        status=AutomationProposalStatus.ACCEPTED,
        reviewed_by="VSCS Acceptance Test",
        accepted_by="VSCS Acceptance Test",
    )

    class Store:
        def __init__(self):
            self.saved = []

        def list_proposals(self):
            return (scene, prior)

        def save(self, proposal):
            self.saved.append(proposal)
            return proposal

    class Provider:
        provider_name = "test-openai"
        model_name = "test-model"

        def propose_scene_shots(self, **_kwargs):
            raise AssertionError("Provider must not be called after human acceptance")

    store = Store()
    service = SceneShotProposalAutomationService(Provider(), store)
    with pytest.raises(ValueError, match="Cannot regenerate"):
        service.generate(
            story_id="STORY-001",
            source_text="An empty room",
            source_revision="source-revision",
            baseline=SimpleNamespace(story_id="STORY-001", source_revision="source-revision"),
        )
    assert store.saved == []
