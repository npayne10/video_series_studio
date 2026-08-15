"""Human review, acceptance and compilation surface for Phase 19.5 automation proposals."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.automation import (
    AutomationCompilationError,
    AutomationProposal,
    AutomationProposalError,
    AutomationProposalService,
    AutomationProposalStatus,
    AutomationProposalType,
    ProposalAcceptanceError,
    ProposalAcceptanceService,
    ProposalAutoCompilationOrchestrator,
)


class AutomationProposalReviewDialog(QDialog):
    """Inspect and explicitly govern current Story automation proposals."""

    PROPOSAL_ID_ROLE = int(Qt.ItemDataRole.UserRole)

    def __init__(
        self,
        proposals: AutomationProposalService,
        *,
        story_id: str,
        source_revision: str,
        acceptance: ProposalAcceptanceService | None = None,
        orchestrator: ProposalAutoCompilationOrchestrator | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._proposals = proposals
        self._acceptance = acceptance
        self._orchestrator = orchestrator
        self.story_id = story_id.strip().upper()
        self.source_revision = source_revision.strip()
        self._proposal_by_id: dict[str, AutomationProposal] = {}
        self._tree_item_by_id: dict[str, QTreeWidgetItem] = {}
        self.setWindowTitle("Automation Proposal Review & Acceptance")
        self.resize(1220, 800)

        layout = QVBoxLayout(self)
        heading = QLabel(
            f"Story: {self.story_id}    Revision: {self.source_revision}\n"
            "Inspect proposals before acceptance. Human acceptance authorizes deterministic "
            "orchestration into existing governed planning authority; it is not final Production "
            "Approval and never authorizes provider submission.",
            self,
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.tree = QTreeWidget(splitter)
        self.tree.setObjectName("automationProposalTree")
        self.tree.setHeaderLabels(["Proposal", "Status", "Runtime"])
        self.tree.setColumnWidth(0, 430)
        self.tree.setColumnWidth(1, 100)
        self.details = QPlainTextEdit(splitter)
        self.details.setObjectName("automationProposalDetails")
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Select a production automation proposal to inspect it.")
        splitter.addWidget(self.tree)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        governance_form = QFormLayout()
        self.reviewer_edit = QLineEdit(self)
        self.reviewer_edit.setObjectName("automationProposalReviewer")
        self.reviewer_edit.setPlaceholderText("Human reviewer / operator name")
        self.review_notes_edit = QLineEdit(self)
        self.review_notes_edit.setObjectName("automationProposalReviewNotes")
        self.review_notes_edit.setPlaceholderText("Optional review notes; required when rejecting")
        governance_form.addRow("Reviewer:", self.reviewer_edit)
        governance_form.addRow("Notes:", self.review_notes_edit)
        layout.addLayout(governance_form)

        action_row = QHBoxLayout()
        self.review_selected_button = QPushButton("Mark Selected Reviewed", self)
        self.review_selected_button.setObjectName("markSelectedProposalReviewed")
        self.accept_selected_button = QPushButton("Accept Selected", self)
        self.accept_selected_button.setObjectName("acceptSelectedProposal")
        self.reject_selected_button = QPushButton("Reject Selected", self)
        self.reject_selected_button.setObjectName("rejectSelectedProposal")
        self.accept_eligible_button = QPushButton("Review & Accept Eligible Set…", self)
        self.accept_eligible_button.setObjectName("acceptEligibleProposalSet")
        self.compile_button = QPushButton("Compile Accepted…", self)
        self.compile_button.setObjectName("compileAcceptedProposals")
        for button in (
            self.review_selected_button,
            self.accept_selected_button,
            self.reject_selected_button,
            self.accept_eligible_button,
            self.compile_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.tree.currentItemChanged.connect(self._selection_changed)
        self.review_selected_button.clicked.connect(self._review_selected)
        self.accept_selected_button.clicked.connect(self._accept_selected)
        self.reject_selected_button.clicked.connect(self._reject_selected)
        self.accept_eligible_button.clicked.connect(self._accept_eligible_set)
        self.compile_button.clicked.connect(self._compile_accepted)
        self.refresh()

    def refresh(self, *, selected_proposal_id: str = "") -> None:
        current_id = selected_proposal_id or self._current_proposal_id()
        self.tree.clear()
        self.details.clear()
        self._tree_item_by_id = {}
        selected = tuple(
            proposal
            for proposal in self._proposals.list_proposals()
            if proposal.provenance.source_story_id == self.story_id
            and proposal.provenance.source_revision == self.source_revision
        )
        self._proposal_by_id = {proposal.proposal_id: proposal for proposal in selected}
        interpretations = self._of_type(selected, AutomationProposalType.STORY_INTERPRETATION)
        assets = self._of_type(selected, AutomationProposalType.ASSET)
        episodes = self._of_type(selected, AutomationProposalType.EPISODE)
        scenes = self._of_type(selected, AutomationProposalType.SCENE)
        shots = self._of_type(selected, AutomationProposalType.SHOT)
        performances = self._of_type(selected, AutomationProposalType.ACTION_PERFORMANCE)
        environments = self._of_type(selected, AutomationProposalType.ENVIRONMENT)
        cameras = self._of_type(selected, AutomationProposalType.CAMERA)
        lighting = self._of_type(selected, AutomationProposalType.LIGHTING)
        continuity = self._of_type(selected, AutomationProposalType.CONTINUITY)

        for proposal in interpretations:
            self.tree.addTopLevelItem(self._item(proposal, prefix="Story Interpretation"))
        if assets:
            asset_root = QTreeWidgetItem(["Canonical Entity & Asset Resolution", "", ""])
            for proposal in sorted(assets, key=self._asset_sort):
                name = str(proposal.payload.get("name", proposal.target_id)).strip()
                category = str(proposal.payload.get("expected_asset_category", "asset")).strip()
                asset_root.addChild(self._item(proposal, prefix=f"{category.title()} — {name}"))
            self.tree.addTopLevelItem(asset_root)

        scene_items: dict[str, QTreeWidgetItem] = {}
        for episode in sorted(episodes, key=self._sequence_sort):
            episode_item = self._item(episode)
            self.tree.addTopLevelItem(episode_item)
            episode_scenes = (
                item
                for item in scenes
                if str(item.payload.get("episode_id", "")) == episode.target_id
            )
            for scene in sorted(episode_scenes, key=self._sequence_sort):
                scene_item = self._item(scene)
                episode_item.addChild(scene_item)
                scene_items[scene.target_id] = scene_item
        for scene in sorted(
            (scene for scene in scenes if scene.target_id not in scene_items),
            key=self._sequence_sort,
        ):
            scene_item = self._item(scene)
            self.tree.addTopLevelItem(scene_item)
            scene_items[scene.target_id] = scene_item

        shot_items: dict[str, QTreeWidgetItem] = {}
        for shot in sorted(shots, key=self._shot_sort):
            parent = scene_items.get(str(shot.payload.get("scene_id", "")))
            shot_item = self._item(shot)
            shot_items[shot.target_id] = shot_item
            if parent is None:
                self.tree.addTopLevelItem(shot_item)
            else:
                parent.addChild(shot_item)

        children = (
            (performances, "Action / Dialogue / Performance"),
            (environments, "Environment Production"),
            (cameras, "Camera Production"),
            (lighting, "Lighting Production"),
            (continuity, "Continuity Awareness"),
        )
        for proposals, label in children:
            for proposal in sorted(proposals, key=lambda item: item.target_id):
                parent = shot_items.get(proposal.target_id)
                item = self._item(proposal, prefix=label)
                if parent is None:
                    self.tree.addTopLevelItem(item)
                else:
                    parent.addChild(item)

        self.tree.expandAll()
        selected_item = self._tree_item_by_id.get(current_id)
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)
        elif self.tree.topLevelItemCount():
            first_item = self.tree.topLevelItem(0)
            if first_item is not None:
                self.tree.setCurrentItem(first_item)
        self._sync_action_state()

    @staticmethod
    def _of_type(
        proposals: tuple[AutomationProposal, ...], proposal_type: AutomationProposalType
    ) -> tuple[AutomationProposal, ...]:
        return tuple(item for item in proposals if item.proposal_type is proposal_type)

    def _item(self, proposal: AutomationProposal, *, prefix: str = "") -> QTreeWidgetItem:
        title = str(proposal.payload.get("title", "")).strip()
        label = prefix or proposal.target_id
        if title:
            label = f"{label} — {title}"
        runtime = proposal.payload.get("target_runtime_seconds", "")
        values = [label, proposal.status.value, f"{runtime}s" if runtime != "" else ""]
        item = QTreeWidgetItem(values)
        item.setData(0, self.PROPOSAL_ID_ROLE, proposal.proposal_id)
        self._tree_item_by_id[proposal.proposal_id] = item
        return item

    def _selection_changed(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if current is None:
            self.details.clear()
            self._sync_action_state()
            return
        proposal = self._proposal_by_id.get(str(current.data(0, self.PROPOSAL_ID_ROLE)))
        if proposal is None:
            self.details.clear()
            self._sync_action_state()
            return
        self.details.setPlainText(self._detail_text(proposal))
        self._sync_action_state()

    def _sync_action_state(self) -> None:
        proposal = self._selected_proposal()
        governance_available = self._acceptance is not None
        self.review_selected_button.setEnabled(
            governance_available
            and proposal is not None
            and proposal.status is AutomationProposalStatus.PROPOSED
        )
        self.accept_selected_button.setEnabled(
            governance_available
            and proposal is not None
            and proposal.status is AutomationProposalStatus.REVIEWED
        )
        self.reject_selected_button.setEnabled(
            governance_available
            and proposal is not None
            and proposal.status
            in {AutomationProposalStatus.PROPOSED, AutomationProposalStatus.REVIEWED}
        )
        self.accept_eligible_button.setEnabled(governance_available)
        self.compile_button.setEnabled(self._orchestrator is not None)

    def _review_selected(self) -> None:
        proposal = self._selected_proposal()
        reviewer = self._reviewer()
        if proposal is None or reviewer is None:
            return
        try:
            self._proposals.mark_reviewed(
                proposal.proposal_id,
                reviewed_by=reviewer,
                notes=self.review_notes_edit.text(),
            )
        except (AutomationProposalError, ValueError) as exc:
            self._error(str(exc))
            return
        self.refresh(selected_proposal_id=proposal.proposal_id)

    def _accept_selected(self) -> None:
        proposal = self._selected_proposal()
        reviewer = self._reviewer()
        if proposal is None or reviewer is None:
            return
        if self._acceptance is not None:
            blocker = self._acceptance._eligibility_blocker(proposal)
            if blocker:
                self._error(blocker)
                return
        try:
            self._proposals.accept(proposal.proposal_id, accepted_by=reviewer)
        except (AutomationProposalError, ValueError) as exc:
            self._error(str(exc))
            return
        self.refresh(selected_proposal_id=proposal.proposal_id)

    def _reject_selected(self) -> None:
        proposal = self._selected_proposal()
        reviewer = self._reviewer()
        if proposal is None or reviewer is None:
            return
        notes = self.review_notes_edit.text().strip()
        if not notes:
            self._error("Rejection notes are required.")
            return
        try:
            self._proposals.reject(
                proposal.proposal_id,
                rejected_by=reviewer,
                notes=notes,
            )
        except (AutomationProposalError, ValueError) as exc:
            self._error(str(exc))
            return
        self.refresh(selected_proposal_id=proposal.proposal_id)

    def _accept_eligible_set(self) -> None:
        if self._acceptance is None:
            self._error("Proposal acceptance service is not registered.")
            return
        reviewer = self._reviewer()
        if reviewer is None:
            return
        answer = QMessageBox.question(
            self,
            "Review & Accept Eligible Proposal Set",
            "This records an explicit human review and accepts every eligible proposal in the "
            "current Story revision. Unresolved canonical assets, continuity conflicts and rejected "
            "proposals remain blocked. Acceptance is not final Production Approval.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            summary = self._acceptance.accept_eligible_current(
                story_id=self.story_id,
                source_revision=self.source_revision,
                reviewed_by=reviewer,
                notes=self.review_notes_edit.text(),
            )
        except (ProposalAcceptanceError, AutomationProposalError, ValueError) as exc:
            self._error(str(exc))
            return
        blocker_preview = self._preview(summary.blockers)
        QMessageBox.information(
            self,
            "Proposal Acceptance Complete",
            f"Accepted now: {summary.accepted_now}\n"
            f"Already accepted: {summary.already_accepted}\n"
            f"Blocked / excluded: {summary.blocked}\n"
            f"Rejected: {summary.rejected}\n\n"
            f"{blocker_preview}",
        )
        self.refresh()

    def _compile_accepted(self) -> None:
        if self._orchestrator is None:
            self._error("Auto-compilation orchestrator is not registered.")
            return
        reviewer = self._reviewer()
        if reviewer is None:
            return
        answer = QMessageBox.question(
            self,
            "Compile Accepted Proposals",
            "This will deterministically materialize accepted Episode, Scene and Shot proposals "
            "through the existing governed planners and promote those accepted structural authorities "
            "to Ready where required for the hierarchy. It will not overwrite differing existing "
            "authority, create canonical assets, perform final Production Approval, or submit to any "
            "provider.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            report = self._orchestrator.compile_current(
                story_id=self.story_id,
                source_revision=self.source_revision,
                compiled_by=reviewer,
            )
        except (AutomationCompilationError, ValueError) as exc:
            self._error(str(exc))
            return
        blocker_preview = self._preview(report.blockers)
        QMessageBox.information(
            self,
            "Accepted Proposal Compilation Complete",
            f"Episodes: {report.episodes_created} created, {report.episodes_reused} reused\n"
            f"Scenes: {report.scenes_created} created, {report.scenes_reused} reused\n"
            f"Shots: {report.shots_created} created, {report.shots_reused} reused\n"
            f"Acceptance-authorized Ready promotions: {report.ready_promotions}\n"
            f"Deferred specialist proposals: {report.deferred_proposals}\n"
            f"Blockers: {report.blocked_proposals}\n\n"
            f"{blocker_preview}\n\n"
            "No final Production Approval or provider submission was performed.",
        )
        self.refresh()

    def _reviewer(self) -> str | None:
        reviewer = self.reviewer_edit.text().strip()
        if reviewer:
            return reviewer
        self._error("Enter the human reviewer / operator name first.")
        return None

    def _selected_proposal(self) -> AutomationProposal | None:
        proposal_id = self._current_proposal_id()
        return self._proposal_by_id.get(proposal_id)

    def _current_proposal_id(self) -> str:
        current = self.tree.currentItem()
        if current is None:
            return ""
        value = current.data(0, self.PROPOSAL_ID_ROLE)
        return str(value) if value is not None else ""

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "Automation Proposal Review", message)

    @staticmethod
    def _preview(values: tuple[str, ...], limit: int = 5) -> str:
        if not values:
            return "No blockers reported."
        shown = list(values[:limit])
        if len(values) > limit:
            shown.append(f"… and {len(values) - limit} more")
        return "Blockers / exclusions:\n" + "\n".join(f"• {value}" for value in shown)

    @staticmethod
    def _detail_text(proposal: AutomationProposal) -> str:
        provenance = proposal.provenance
        lines = [
            f"Proposal ID: {proposal.proposal_id}",
            f"Type: {proposal.proposal_type.value}",
            f"Target: {proposal.target_id}",
            f"Status: {proposal.status.value}",
            "",
            "HUMAN GOVERNANCE",
            f"Reviewed by: {proposal.reviewed_by}",
            f"Accepted by: {proposal.accepted_by}",
            f"Rejected by: {proposal.rejected_by}",
            f"Review notes: {proposal.review_notes}",
            "",
            "PROPOSAL CONTENT",
            json.dumps(proposal.payload, indent=2, ensure_ascii=False, default=str),
            "",
            "PROVENANCE",
            f"Source kind: {provenance.source_kind.value}",
            f"Story ID: {provenance.source_story_id}",
            f"Story revision: {provenance.source_revision}",
            f"Source scope: {provenance.source_scope}",
            f"Provider: {provenance.provider}",
            f"Model: {provenance.model}",
            f"Confidence: {provenance.confidence:.3f}",
            f"Resolution: {provenance.resolution_method}",
            f"Inference note: {provenance.inference_note}",
            "",
            "METADATA",
            json.dumps(proposal.metadata, indent=2, ensure_ascii=False, default=str),
        ]
        return "\n".join(lines)

    @staticmethod
    def _sequence_sort(proposal: AutomationProposal) -> tuple[int, str]:
        value = proposal.payload.get("sequence_number", 0)
        sequence = value if isinstance(value, int) and not isinstance(value, bool) else 0
        return sequence, proposal.target_id

    @staticmethod
    def _asset_sort(proposal: AutomationProposal) -> tuple[str, str, str]:
        category = str(proposal.payload.get("expected_asset_category", ""))
        name = str(proposal.payload.get("name", ""))
        return category, name.casefold(), proposal.target_id

    @staticmethod
    def _shot_sort(proposal: AutomationProposal) -> tuple[str, int, str]:
        scene_id = str(proposal.payload.get("scene_id", ""))
        sequence, target_id = AutomationProposalReviewDialog._sequence_sort(proposal)
        return scene_id, sequence, target_id
