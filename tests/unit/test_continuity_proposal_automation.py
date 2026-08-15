from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    ContinuityProposalAutomationService,
)
from vscs.application.projects import ProjectService
from vscs.infrastructure.configuration import ConfigurationService


def _service(
    tmp_path: Path,
) -> tuple[ContinuityProposalAutomationService, AutomationProposalService]:
    configuration = ConfigurationService(tmp_path / "settings.toml")
    projects = ProjectService(configuration)
    projects.create(tmp_path / "Project", name="Project")
    store = AutomationProposalService(projects)
    provenance = AutomationProvenance(
        source_kind=AutomationSourceKind.AI_INFERENCE,
        source_story_id="STORY-001",
        source_revision="rev-1",
        source_scope="test",
        provider="test",
        model="test",
    )
    for index in (1, 2):
        shot_id = f"EP-001-SC-001-SHT-{index:03d}"
        store.save(
            AutomationProposal(
                proposal_id=f"AUT-SHOT-{index}",
                proposal_type=AutomationProposalType.SHOT,
                target_id=shot_id,
                payload={"scene_id": "EP-001-SC-001", "sequence_number": index},
                provenance=provenance,
            )
        )
        store.save(
            AutomationProposal(
                proposal_id=f"AUT-PERF-{index}",
                proposal_type=AutomationProposalType.ACTION_PERFORMANCE,
                target_id=shot_id,
                payload={
                    "opening_state": "Series entry" if index == 1 else "same as previous shot",
                    "closing_state": "James at console"
                    if index == 1
                    else "James turns toward Cheryl",
                },
                provenance=provenance,
            )
        )
        store.save(
            AutomationProposal(
                proposal_id=f"AUT-ENV-{index}",
                proposal_type=AutomationProposalType.ENVIRONMENT,
                target_id=shot_id,
                payload={"environment_context": "interior", "surface_state": "Bridge"},
                provenance=provenance,
            )
        )
        store.save(
            AutomationProposal(
                proposal_id=f"AUT-CAM-{index}",
                proposal_type=AutomationProposalType.CAMERA,
                target_id=shot_id,
                payload={
                    "screen_direction": "left_to_right" if index == 1 else "preserve_previous"
                },
                provenance=provenance,
            )
        )
        store.save(
            AutomationProposal(
                proposal_id=f"AUT-LIGHT-{index}",
                proposal_type=AutomationProposalType.LIGHTING,
                target_id=shot_id,
                payload={"continuity_notes": "Maintain bridge practical lighting"},
                provenance=provenance,
            )
        )
    return ContinuityProposalAutomationService(store), store


def test_continuity_automation_inherits_previous_closing_state(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    generated = service.generate(
        story_id="STORY-001", source_text="Bridge sequence", source_revision="rev-1"
    )
    assert len(generated) == 2
    first, second = generated
    assert first.proposal_type is AutomationProposalType.CONTINUITY
    assert first.payload["inheritance_mode"] == "series-entry"
    assert second.payload["previous_shot_id"] == first.target_id
    assert second.payload["previous_closing_state"] == "James at console"
    assert second.payload["effective_opening_state"] == "James at console"
    assert second.payload["opening_resolution"] == "preserve-previous-directive"
    assert second.payload["continuity_conflicts"] == []
    assert second.provenance.source_kind is AutomationSourceKind.DETERMINISTIC_RESOLUTION
    assert not second.consumable
    assert len(store.list_proposals()) == 12


def test_continuity_automation_exposes_conflict_for_human_review(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    performance = next(item for item in store.list_proposals() if item.proposal_id == "AUT-PERF-2")
    store.save(
        AutomationProposal(
            proposal_id=performance.proposal_id,
            proposal_type=performance.proposal_type,
            target_id=performance.target_id,
            payload={
                "opening_state": "James is suddenly at the hatch",
                "closing_state": "James turns toward Cheryl",
            },
            provenance=performance.provenance,
        )
    )
    generated = service.generate(
        story_id="STORY-001", source_text="Bridge sequence", source_revision="rev-1"
    )
    assert generated[1].payload["continuity_conflicts"]
    assert generated[1].payload["effective_opening_state"] == "James is suddenly at the hatch"


def test_continuity_automation_requires_current_camera_and_lighting(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    store._write(
        tuple(
            item
            for item in store.list_proposals()
            if item.proposal_type is not AutomationProposalType.LIGHTING
        )
    )
    with pytest.raises(ValueError, match="Lighting proposals"):
        service.generate(
            story_id="STORY-001", source_text="Bridge sequence", source_revision="rev-1"
        )
