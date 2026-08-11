"""Human review UI for the complete governed Phase 19.3 Shot plan."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.story import (
    GovernedPlanningReviewService,
    PlanningReviewError,
    PlanningReviewStatus,
    ShotPlan,
)


class GovernedPlanningReviewDialog(QDialog):
    """Review Shot, Asset, Camera, Lighting and Environment authority in one gate."""

    def __init__(
        self,
        service: GovernedPlanningReviewService,
        shot: ShotPlan,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.shot = shot
        self.setWindowTitle(f"Planning Review — {shot.shot_id}")
        self.resize(860, 620)
        self.setMinimumSize(720, 520)

        root = QVBoxLayout(self)
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.checks = QTableWidget(0, 3, self)
        self.checks.setHorizontalHeaderLabels(("Planning Area", "Result", "Detail"))
        self.checks.horizontalHeader().setStretchLastSection(True)
        self.checks.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.checks, 1)

        root.addWidget(QLabel("Reviewer notes", self))
        self.notes = QTextEdit(self)
        self.notes.setPlaceholderText(
            "Record human review observations only. Upstream plans remain authoritative."
        )
        root.addWidget(self.notes)

        actions = QHBoxLayout()
        self.create_button = QPushButton("Start Review", self)
        self.save_button = QPushButton("Save Notes", self)
        self.approve_button = QPushButton("Approve Planning", self)
        self.draft_button = QPushButton("Return to Draft", self)
        for button in (
            self.create_button,
            self.save_button,
            self.approve_button,
            self.draft_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_box.rejected.connect(self.reject)
        root.addWidget(close_box)

        self.create_button.clicked.connect(self._create)
        self.save_button.clicked.connect(self._save)
        self.approve_button.clicked.connect(self._approve)
        self.draft_button.clicked.connect(self._return_to_draft)
        self.refresh()

    def refresh(self) -> None:
        snapshot = self.service.snapshot(self.shot.shot_id)
        review = self.service.review(self.shot.shot_id)
        self.checks.setRowCount(len(snapshot.checks))
        for row, check in enumerate(snapshot.checks):
            self.checks.setItem(row, 0, QTableWidgetItem(check.area))
            self.checks.setItem(row, 1, QTableWidgetItem(check.status.value.upper()))
            self.checks.setItem(row, 2, QTableWidgetItem(check.detail))

        if review is None:
            state = "Not started"
            self.notes.clear()
        else:
            current = self.service.is_current(review)
            state = review.status.value.title()
            if review.status is PlanningReviewStatus.APPROVED and not current:
                state += " / Stale"
            self.notes.setPlainText(review.reviewer_notes)

        readiness = "READY FOR APPROVAL" if snapshot.is_ready else "BLOCKED"
        self.summary.setText(
            f"<b>{self.shot.shot_id} — {self.shot.title}</b><br>"
            f"Review: {state} &nbsp; | &nbsp; Current planning: {readiness}<br>"
            "This gate reviews authoritative planning only; it does not edit Shot, Asset, "
            "Camera, Lighting or Environment contracts."
        )
        approved = review is not None and review.status is PlanningReviewStatus.APPROVED
        self.create_button.setEnabled(review is None)
        self.notes.setReadOnly(approved)
        self.save_button.setEnabled(review is not None and not approved)
        self.approve_button.setEnabled(review is not None and not approved and snapshot.is_ready)
        self.draft_button.setEnabled(approved)

    def _create(self) -> None:
        self._run(
            lambda: self.service.create(
                self.shot.shot_id,
                reviewer_notes=self.notes.toPlainText(),
            )
        )

    def _save(self) -> None:
        self._run(lambda: self.service.update_notes(self.shot.shot_id, self.notes.toPlainText()))

    def _approve(self) -> None:
        self._run(lambda: self.service.approve(self.shot.shot_id))

    def _return_to_draft(self) -> None:
        self._run(lambda: self.service.return_to_draft(self.shot.shot_id))

    def _run(self, action: Callable[[], object]) -> None:
        try:
            action()
        except PlanningReviewError as exc:
            QMessageBox.warning(self, "Planning Review", str(exc))
        self.refresh()
