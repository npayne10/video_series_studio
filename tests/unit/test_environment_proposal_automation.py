from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    EnvironmentProposalAutomationService,
    TemplateEnvironmentProposalProvider,
)
from vscs.application.projects import ProjectService
from vscs.infrastructure.configuration import ConfigurationService


def _store(tmp_path: Path) -> AutomationProposalService:
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    projects = ProjectService(configuration)
    projects.create(tmp_path / "project", name="Environment Test")
    return AutomationProposalService(projects)


def _provenance(revision: str = "rev-1") -> AutomationProvenance:
    return AutomationProvenance(
        source_kind=AutomationSourceKind.AI_INFERENCE,
        source_story_id="STORY-001",
        source_revision=revision,
        source_scope="test",
        provider="test",
        model="test",
    )


def _seed_current_prerequisites(store: AutomationProposalService) -> None:
    store.save(
        AutomationProposal(
            proposal_id="AUT-SHOT-1",
            proposal_type=AutomationProposalType.SHOT,
            target_id="EP-001-SC-001-SHT-001",
            payload={
                "scene_id": "EP-001-SC-001",
                "required_action": "James crosses the bridge.",
                "continuity_in": "Bridge entry",
                "continuity_out": "Command console",
            },
            provenance=_provenance(),
        )
    )
    store.save(
        AutomationProposal(
            proposal_id="AUT-ACTION-1",
            proposal_type=AutomationProposalType.ACTION_PERFORMANCE,
            target_id="EP-001-SC-001-SHT-001",
            payload={
                "temporal_narrative": "James crosses the bridge.",
                "opening_state": "Bridge entry",
                "closing_state": "Command console",
            },
            provenance=_provenance(),
        )
    )


def test_environment_automation_creates_reviewable_proposal_without_authority(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    _seed_current_prerequisites(store)
    service = EnvironmentProposalAutomationService(TemplateEnvironmentProposalProvider(), store)

    generated = service.generate(
        story_id="STORY-001",
        source_text="James crosses the bridge toward the command console.",
        source_revision="rev-1",
    )

    assert len(generated) == 1
    proposal = generated[0]
    assert proposal.proposal_type is AutomationProposalType.ENVIRONMENT
    assert proposal.status.value == "proposed"
    assert not proposal.consumable
    assert proposal.target_id == "EP-001-SC-001-SHT-001"
    assert proposal.payload["gravity_m_s2"] is None
    assert proposal.payload["pressure_kpa"] is None
    assert proposal.metadata["parent_shot_proposal_id"] == "AUT-SHOT-1"
    assert proposal.metadata["parent_action_performance_proposal_id"] == "AUT-ACTION-1"


def test_environment_automation_requires_current_performance_proposals(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(
        AutomationProposal(
            proposal_id="AUT-SHOT-1",
            proposal_type=AutomationProposalType.SHOT,
            target_id="EP-001-SC-001-SHT-001",
            payload={"required_action": "James crosses the bridge."},
            provenance=_provenance(),
        )
    )
    service = EnvironmentProposalAutomationService(TemplateEnvironmentProposalProvider(), store)

    with pytest.raises(ValueError, match="Action/Performance proposals"):
        service.generate(
            story_id="STORY-001",
            source_text="James crosses the bridge.",
            source_revision="rev-1",
        )


def test_environment_automation_rejects_stale_prerequisites(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed_current_prerequisites(store)
    service = EnvironmentProposalAutomationService(TemplateEnvironmentProposalProvider(), store)

    with pytest.raises(ValueError, match="Shot proposals"):
        service.generate(
            story_id="STORY-001",
            source_text="Revised Story",
            source_revision="rev-2",
        )
