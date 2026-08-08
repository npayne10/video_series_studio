"""Read-only Story Analysis integration acceptance report dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.story import StoryRecord
from vscs.application.story_analysis import (
    AcceptanceLevel,
    StoryAnalysisAcceptanceReport,
    StoryAnalysisAcceptanceService,
)


class StoryAnalysisAcceptanceDialog(QDialog):
    """Display subsystem health separately from production-readiness warnings."""

    def __init__(
        self,
        story: StoryRecord,
        service: StoryAnalysisAcceptanceService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.story = story
        self.service = service
        self.report: StoryAnalysisAcceptanceReport | None = None
        self.setObjectName("storyAnalysisAcceptanceDialog")
        self.setWindowTitle(f"Story Analysis Acceptance — {story.title}")
        self.resize(1050, 680)

        root = QVBoxLayout(self)
        self.summary = QLabel(self)
        self.summary.setObjectName("storyAnalysisAcceptanceSummary")
        self.summary.setStyleSheet("font-size: 16px; font-weight: 600;")
        root.addWidget(self.summary)

        self.metadata = QLabel(self)
        self.metadata.setObjectName("storyAnalysisAcceptanceMetadata")
        root.addWidget(self.metadata)

        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("storyAnalysisAcceptanceTable")
        self.table.setHorizontalHeaderLabels(("Result", "Check", "Detail", "ID"))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        refresh = QPushButton("Refresh Acceptance Report", self)
        refresh.setObjectName("refreshStoryAnalysisAcceptance")
        refresh.setToolTip(
            "Re-evaluate persisted artifacts without rerunning Story Analysis or AI."
        )
        refresh.clicked.connect(self.refresh_report)
        actions.addWidget(refresh)
        close = QPushButton("Close", self)
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        root.addLayout(actions)

        self.refresh_report()

    def refresh_report(self) -> None:
        """Refresh read-only health checks; this method never executes Story Analysis."""
        self.report = self.service.evaluate(self.story)
        self._populate()

    def _populate(self) -> None:
        report = self.report
        if report is None:
            return
        if report.failed:
            state = "FAILED"
        elif report.warnings:
            state = "PASSED WITH WARNINGS"
        else:
            state = "PASSED"
        self.summary.setText(f"Story Analysis Integration Acceptance: {state}")
        self.metadata.setText(
            f"Cache: {report.cache_state.value} | Analysis version: {report.analysis_version} | "
            f"Provider: {report.provider} | Shot Planning: "
            f"{'READY' if report.ready_for_shot_planning else 'NOT READY'} | "
            f"Generation: {'READY' if report.ready_for_generation else 'NOT READY'}"
        )
        self.table.setRowCount(0)
        for check in report.checks:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = (
                self._label(check.level),
                check.title,
                check.detail,
                check.check_id,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

    @staticmethod
    def _label(level: AcceptanceLevel) -> str:
        if level is AcceptanceLevel.PASS:
            return "PASS"
        if level is AcceptanceLevel.WARNING:
            return "WARNING"
        return "FAIL"
