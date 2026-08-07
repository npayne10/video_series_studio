"""Human review surface for AI-proposed story production entities."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.story import StoryRecord
from vscs.application.story_analysis import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    AnalysisStatus,
    ApprovedStoryIntelligenceService,
    StoryAnalysisEngine,
    StoryAnalysisRequest,
    StoryIntelligenceError,
    StorySourceReader,
)
from vscs.domain.story_analysis import (
    CandidateReviewStatus,
    EntityCandidate,
    EntityResolutionResult,
)


class AIEntityReviewDialog(QDialog):
    """Review, persist, approve, or reject AI-proposed production entities."""

    def __init__(
        self,
        story: StoryRecord,
        engine: StoryAnalysisEngine,
        parent: QWidget | None = None,
        *,
        intelligence: ApprovedStoryIntelligenceService | None = None,
    ) -> None:
        super().__init__(parent)
        self.story = story
        self.engine = engine
        self.intelligence = intelligence
        self.result: EntityResolutionResult | None = None
        self.setObjectName("aiEntityReviewDialog")
        self.setWindowTitle(f"AI Entity Review — {story.title}")
        self.resize(1180, 720)
        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                "AI-detected production entities remain proposals until approved. "
                "Approved decisions are persisted as Story Intelligence. Existing XPD matches "
                "are linked to canon; approved new entities become Draft canonical assets.",
                self,
            )
        )
        self.table = QTableWidget(0, 7, self)
        self.table.setObjectName("aiEntityCandidateTable")
        self.table.setHorizontalHeaderLabels(
            ("Status", "Type", "Name", "Confidence", "Resolution", "XPD Match", "Description")
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.approve_button = QPushButton("Approve Candidate", self)
        self.reject_button = QPushButton("Reject Candidate", self)
        self.reset_button = QPushButton("Reset to Proposed", self)
        self.refresh_button = QPushButton("Re-run AI Analysis", self)
        self.approve_button.clicked.connect(self._approve)
        self.reject_button.clicked.connect(self._reject)
        self.reset_button.clicked.connect(self._reset)
        self.refresh_button.clicked.connect(self.refresh_analysis)
        for button in (
            self.approve_button,
            self.reject_button,
            self.reset_button,
            self.refresh_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.summary = QLabel(self)
        self.summary.setObjectName("aiEntityReviewSummary")
        root.addWidget(self.summary)
        self.refresh_analysis()

    def refresh_analysis(self) -> None:
        try:
            source_text = StorySourceReader().read(self.story)
        except Exception as exc:
            QMessageBox.critical(self, "AI Entity Review", str(exc))
            return
        report = self.engine.analyze(
            StoryAnalysisRequest(
                story_id=self.story.story_id,
                source_text=source_text,
                source_revision=self.story.updated_at or None,
                metadata={"title": self.story.title},
            )
        )
        if report.status is not AnalysisStatus.COMPLETED:
            QMessageBox.critical(
                self,
                "AI Entity Review",
                "\n".join(report.diagnostics) or "AI Story Analysis failed.",
            )
            return
        resolution = report.artifacts.get(AI_ENTITY_RESOLUTION_ARTIFACT)
        if not isinstance(resolution, EntityResolutionResult):
            QMessageBox.warning(
                self,
                "AI Entity Review",
                "AI enrichment is not available. Check the configured AI provider.",
            )
            return
        try:
            if self.intelligence is not None:
                self.intelligence.save_metadata(resolution)
                resolution = self.intelligence.restore(resolution)
        except StoryIntelligenceError as exc:
            QMessageBox.critical(self, "Story Intelligence", str(exc))
            return
        self.result = resolution
        self._populate()

    def _populate(self) -> None:
        self.table.setRowCount(0)
        if self.result is None:
            return
        for row, candidate in enumerate(self.result.candidates):
            self.table.insertRow(row)
            values = (
                candidate.review_status.value,
                candidate.category.value,
                candidate.name,
                f"{candidate.confidence:.0%}",
                candidate.match_kind.value.replace("_", " "),
                candidate.matched_asset_id or "New entity",
                candidate.description,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, candidate.candidate_id)
                self.table.setItem(row, column, item)
        pending = len(self.result.pending_candidates)
        approved = sum(
            1
            for item in self.result.candidates
            if item.review_status is CandidateReviewStatus.APPROVED
        )
        rejected = sum(
            1
            for item in self.result.candidates
            if item.review_status is CandidateReviewStatus.REJECTED
        )
        matched = sum(1 for item in self.result.candidates if item.matched_asset_id)
        self.summary.setText(
            f"{len(self.result.candidates)} candidates — {pending} awaiting review — "
            f"{approved} approved — {rejected} rejected — {matched} XPD-linked"
        )
        self.table.resizeColumnsToContents()

    def _selected_candidate(self) -> EntityCandidate | None:
        if self.result is None:
            return None
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        candidate_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        return next(
            (
                candidate
                for candidate in self.result.candidates
                if candidate.candidate_id == candidate_id
            ),
            None,
        )

    def _replace(self, updated: EntityCandidate) -> None:
        if self.result is None:
            return
        candidates = tuple(
            updated if candidate.candidate_id == updated.candidate_id else candidate
            for candidate in self.result.candidates
        )
        self.result = self.result.model_copy(update={"candidates": candidates})
        self._populate()

    def _approve(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None or self.result is None:
            return
        if self.intelligence is None:
            self._replace(candidate.approve())
            return
        if candidate.matched_asset_id is None:
            answer = QMessageBox.question(
                self,
                "Approve New Canonical Entity",
                f"Approve '{candidate.name}' as a new canonical production entity?\n\n"
                "VSCS will create a Draft XPD asset. CAP/production readiness will still "
                "require the normal approval workflow.",
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return
        try:
            updated = self.intelligence.approve(self.result, candidate)
        except Exception as exc:
            QMessageBox.critical(self, "Story Intelligence", str(exc))
            return
        self._replace(updated)

    def _reject(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None or self.result is None:
            return
        if self.intelligence is None:
            self._replace(candidate.reject())
            return
        try:
            updated = self.intelligence.reject(self.result, candidate)
        except StoryIntelligenceError as exc:
            QMessageBox.critical(self, "Story Intelligence", str(exc))
            return
        self._replace(updated)

    def _reset(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None or self.result is None:
            return
        if self.intelligence is None:
            self._replace(
                candidate.model_copy(update={"review_status": CandidateReviewStatus.PROPOSED})
            )
            return
        try:
            updated = self.intelligence.reset(self.result, candidate)
        except StoryIntelligenceError as exc:
            QMessageBox.critical(self, "Story Intelligence", str(exc))
            return
        self._replace(updated)
