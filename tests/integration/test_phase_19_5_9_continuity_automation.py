from __future__ import annotations

from pathlib import Path

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    ContinuityProposalAutomationService,
)
from vscs.application.continuity_compiler import ContinuityCompilerService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.toml",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def test_continuity_automation_is_registered_with_story_workspace(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)
        service = application.services.get(ContinuityProposalAutomationService)
        assert isinstance(service, ContinuityProposalAutomationService)
        assert not window.story_browser.continuity_proposals_button.isHidden()
        assert window.story_browser.continuity_proposals_button.text() == "Continuity Proposals…"


def test_continuity_proposals_do_not_create_governed_continuity_compilation(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)
        store = application.services.require(AutomationProposalService)
        provenance = AutomationProvenance(
            source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope="integration",
            provider="vscs-template",
            model="deterministic",
        )
        shot_id = "EP-001-SC-001-SHT-001"
        definitions = (
            ("SHOT", AutomationProposalType.SHOT, {"scene_id": "EP-001-SC-001", "sequence_number": 1}),
            ("PERF", AutomationProposalType.ACTION_PERFORMANCE, {"opening_state": "Bridge entry", "closing_state": "At console"}),
            ("ENV", AutomationProposalType.ENVIRONMENT, {"environment_context": "interior", "surface_state": "Bridge"}),
            ("CAM", AutomationProposalType.CAMERA, {"screen_direction": "preserve_previous"}),
            ("LIGHT", AutomationProposalType.LIGHTING, {"continuity_notes": "Maintain practical bridge lighting"}),
        )
        for proposal_id, proposal_type, payload in definitions:
            store.save(AutomationProposal(
                proposal_id=proposal_id,
                proposal_type=proposal_type,
                target_id=shot_id,
                payload=payload,
                provenance=provenance,
            ))
        authority = application.services.require(ContinuityCompilerService)
        before = authority.list_drafts()
        generated = application.services.require(ContinuityProposalAutomationService).generate(
            story_id="STORY-001", source_text="Bridge sequence", source_revision="rev-1"
        )
        assert len(generated) == 1
        assert generated[0].proposal_type is AutomationProposalType.CONTINUITY
        assert authority.list_drafts() == before
