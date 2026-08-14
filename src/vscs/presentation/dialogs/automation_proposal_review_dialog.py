"""Read-only review surface for governed Phase 19.5 automation proposals."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
)


class AutomationProposalReviewDialog(QDialog):
    """Inspect current Story automation proposals without mutating any authority."""

    PROPOSAL_ID_ROLE = int(Qt.ItemDataRole.UserRole)

    def __init__(
        self,
        proposals: AutomationProposalService,
        *,
        story_id: str,
        source_revision: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._proposals = proposals
        self.story_id = story_id.strip().upper()
        self.source_revision = source_revision.strip()
        self._proposal_by_id: dict[str, AutomationProposal] = {}
        self.setWindowTitle("Automation Proposal Review")
        self.resize(1100, 720)
        layout = QVBoxLayout(self)
        heading = QLabel(
            f"Story: {self.story_id}    Revision: {self.source_revision}\n"
            "Read-only automation proposals. Reviewing here does not accept, create, mark Ready, "
            "or approve production authority.",
            self,
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.tree = QTreeWidget(splitter)
        self.tree.setObjectName("automationProposalTree")
        self.tree.setHeaderLabels(["Proposal", "Status", "Runtime"])
        self.tree.setColumnWidth(0, 390)
        self.tree.setColumnWidth(1, 100)
        self.details = QPlainTextEdit(splitter)
        self.details.setObjectName("automationProposalDetails")
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(
            "Select a Story, Asset, Episode, Scene, Shot, Performance or Environment proposal."
        )
        splitter.addWidget(self.tree)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.tree.currentItemChanged.connect(self._selection_changed)
        self.refresh()

    def refresh(self) -> None:
        """Reload current-revision proposals from the project proposal store."""
        self.tree.clear()
        self.details.clear()
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
            scene_id = str(shot.payload.get("scene_id", ""))
            parent = scene_items.get(scene_id)
            shot_item = self._item(shot)
            shot_items[shot.target_id] = shot_item
            if parent is None:
                self.tree.addTopLevelItem(shot_item)
            else:
                parent.addChild(shot_item)

        for performance in sorted(performances, key=lambda item: item.target_id):
            parent = shot_items.get(performance.target_id)
            item = self._item(performance, prefix="Action / Dialogue / Performance")
            if parent is None:
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
        for environment in sorted(environments, key=lambda item: item.target_id):
            parent = shot_items.get(environment.target_id)
            item = self._item(environment, prefix="Environment Production")
            if parent is None:
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)

        self.tree.expandAll()
        if self.tree.topLevelItemCount():
            first_item = self.tree.topLevelItem(0)
            if first_item is not None:
                self.tree.setCurrentItem(first_item)

    @staticmethod
    def _of_type(
        proposals: tuple[AutomationProposal, ...],
        proposal_type: AutomationProposalType,
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
        return item

    def _selection_changed(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        if current is None:
            self.details.clear()
            return
        proposal_id = current.data(0, self.PROPOSAL_ID_ROLE)
        proposal = self._proposal_by_id.get(str(proposal_id))
        if proposal is None:
            self.details.clear()
            return
        self.details.setPlainText(self._detail_text(proposal))

    @staticmethod
    def _detail_text(proposal: AutomationProposal) -> str:
        provenance = proposal.provenance
        lines = [
            f"Proposal ID: {proposal.proposal_id}",
            f"Type: {proposal.proposal_type.value}",
            f"Target: {proposal.target_id}",
            f"Status: {proposal.status.value}",
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
