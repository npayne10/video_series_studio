from __future__ import annotations

from pathlib import Path

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    ProposalAcceptanceService,
)
from vscs.application.projects import ProjectService
from vscs.infrastructure.configuration import ConfigurationService
from vscs.presentation.dialogs.automation_proposal_review_dialog import (
    AutomationProposalReviewDialog,
)


def test_review_dialog_supports_explicit_review_then_acceptance(tmp_path: Path, qtbot) -> None:
    configuration = ConfigurationService(tmp_path / "settings.toml")
    projects = ProjectService(configuration)
    projects.create(tmp_path / "Project", name="Project")
    store = AutomationProposalService(projects)
    store.save(
        AutomationProposal(
            proposal_id="AUT-EPISODE-1",
            proposal_type=AutomationProposalType.EPISODE,
            target_id="EP-001",
            payload={
                "sequence_number": 1,
                "title": "The Silent Relay",
                "target_runtime_seconds": 60,
            },
            provenance=AutomationProvenance(
                source_kind=AutomationSourceKind.AI_INFERENCE,
                source_story_id="STORY-001",
                source_revision="rev-1",
                source_scope="test",
                provider="test",
                model="test",
            ),
        )
    )
    dialog = AutomationProposalReviewDialog(
        store,
        story_id="STORY-001",
        source_revision="rev-1",
        acceptance=ProposalAcceptanceService(store),
    )
    qtbot.addWidget(dialog)
    dialog.reviewer_edit.setText("Neill")

    assert dialog.review_selected_button.isEnabled()
    assert not dialog.accept_selected_button.isEnabled()
    dialog._review_selected()
    assert store.proposal("AUT-EPISODE-1").status is AutomationProposalStatus.REVIEWED
    assert dialog.accept_selected_button.isEnabled()

    dialog._accept_selected()
    accepted = store.proposal("AUT-EPISODE-1")
    assert accepted.status is AutomationProposalStatus.ACCEPTED
    assert accepted.reviewed_by == "Neill"
    assert accepted.accepted_by == "Neill"
    assert not dialog.accept_selected_button.isEnabled()
