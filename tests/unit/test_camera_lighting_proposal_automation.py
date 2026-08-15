from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    CameraLightingProposalAutomationService,
    TemplateCameraLightingProposalProvider,
)
from vscs.application.projects import ProjectService
from vscs.infrastructure.configuration import ConfigurationService


def _service(tmp_path: Path) -> tuple[CameraLightingProposalAutomationService, AutomationProposalService]:
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
    store.save(AutomationProposal(
        proposal_id="AUT-SHOT-1", proposal_type=AutomationProposalType.SHOT,
        target_id="EP-001-SC-001-SHT-001",
        payload={"required_action": "James crosses the bridge.", "dialogue_requirement": "", "continuity_in": "Bridge entrance"},
        provenance=provenance,
    ))
    store.save(AutomationProposal(
        proposal_id="AUT-PERF-1", proposal_type=AutomationProposalType.ACTION_PERFORMANCE,
        target_id="EP-001-SC-001-SHT-001",
        payload={"temporal_narrative": "James crosses the bridge.", "opening_state": "Bridge entrance", "closing_state": "Command console"},
        provenance=provenance,
    ))
    store.save(AutomationProposal(
        proposal_id="AUT-ENV-1", proposal_type=AutomationProposalType.ENVIRONMENT,
        target_id="EP-001-SC-001-SHT-001",
        payload={"environment_context": "interior", "continuity_notes": "Controlled ship interior"},
        provenance=provenance,
    ))
    return CameraLightingProposalAutomationService(TemplateCameraLightingProposalProvider(), store), store


def test_camera_lighting_automation_creates_paired_reviewable_proposals(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    generated = service.generate(story_id="STORY-001", source_text="James crosses the bridge.", source_revision="rev-1")
    assert len(generated) == 2
    camera, lighting = generated
    assert camera.proposal_type is AutomationProposalType.CAMERA
    assert lighting.proposal_type is AutomationProposalType.LIGHTING
    assert camera.target_id == lighting.target_id == "EP-001-SC-001-SHT-001"
    assert camera.payload["camera_profile_asset_id"] == ""
    assert lighting.payload["lighting_profile_asset_id"] == ""
    assert camera.status.value == "proposed" and not camera.consumable
    assert lighting.status.value == "proposed" and not lighting.consumable
    assert lighting.metadata["parent_camera_proposal_id"] == camera.proposal_id
    assert len(store.list_proposals()) == 5


def test_camera_lighting_requires_current_environment_proposal(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    projects = store.projects
    store_without_environment = AutomationProposalService(projects)
    environment = next(item for item in store_without_environment.list_proposals() if item.proposal_type is AutomationProposalType.ENVIRONMENT)
    store_without_environment._write(tuple(item for item in store_without_environment.list_proposals() if item.proposal_id != environment.proposal_id))
    service = CameraLightingProposalAutomationService(TemplateCameraLightingProposalProvider(), store_without_environment)
    with pytest.raises(ValueError, match="Environment proposals"):
        service.generate(story_id="STORY-001", source_text="Story", source_revision="rev-1")


def test_camera_lighting_rejects_stale_story_revision(tmp_path: Path) -> None:
    service, _store = _service(tmp_path)
    with pytest.raises(ValueError, match="Shot proposals"):
        service.generate(story_id="STORY-001", source_text="Story", source_revision="rev-2")
