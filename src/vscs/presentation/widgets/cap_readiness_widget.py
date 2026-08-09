"""CAP readiness presentation for deterministic production-gate reports."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps import (
    CAPReadinessService,
    ProductionProjectionService,
    ReferenceLibraryService,
)
from vscs.domain.caps import ReadinessAssessment, ReadinessReport, ReadinessSeverity
from vscs.presentation.widgets.cap_structured_knowledge import install_structured_cap_editor
from vscs.presentation.widgets.cap_structured_migration import install_modernise_cap_action
from vscs.presentation.widgets.cap_ui_refactoring import (
    install_cap_editor_contract_refactoring,
    install_cap_workspace_refactoring,
)


class CAPReadinessDialog(QDialog):
    """Display the authoritative typed readiness report for one CAP."""

    def __init__(self, report: ReadinessReport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.report = report
        self.setWindowTitle(f"CAP Readiness — {report.asset_id}")
        self.setMinimumWidth(720)

        overall = QProgressBar()
        overall.setRange(0, 100)
        overall.setValue(report.overall_score)
        overall.setFormat("Overall Readiness %p%")
        overall.setObjectName("overallReadinessProgress")

        grid = QGridLayout()
        for row, assessment in enumerate(report.assessments):
            self._add_assessment(grid, row, assessment)

        blockers = QLabel(self._gap_text(report))
        blockers.setWordWrap(True)
        blockers.setObjectName("readinessBlockingIssues")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(overall)
        layout.addLayout(grid)
        layout.addWidget(QLabel("Blocking issues and warnings"))
        layout.addWidget(blockers)
        layout.addWidget(buttons)

    @staticmethod
    def _add_assessment(
        grid: QGridLayout,
        row: int,
        assessment: ReadinessAssessment,
    ) -> None:
        name = QLabel(assessment.dimension.value.replace("_", " ").title())
        state = QLabel(assessment.state.value.replace("_", " ").upper())
        score = QProgressBar()
        score.setRange(0, 100)
        score.setValue(assessment.score)
        score.setFormat("%p%")
        grid.addWidget(name, row, 0)
        grid.addWidget(state, row, 1)
        grid.addWidget(score, row, 2)

    @staticmethod
    def _gap_text(report: ReadinessReport) -> str:
        lines: list[str] = []
        for assessment in report.assessments:
            for gap in assessment.gaps:
                marker = "BLOCK" if gap.severity is ReadinessSeverity.BLOCKING else "WARN"
                lines.append(f"• [{marker}] {gap.message}")
        return "\n".join(lines) if lines else "No readiness gaps."


def install_cap_readiness(
    cap_manager: QWidget,
    projection_service: ProductionProjectionService | None = None,
) -> QPushButton | None:
    """Attach readiness and the production-contract workspace to a CAP Manager."""
    references = getattr(cap_manager, "references", None)
    caps = getattr(cap_manager, "caps", None)
    if references is None or caps is None:
        return None

    if projection_service is None:
        library = ReferenceLibraryService(references)
        service = CAPReadinessService(caps, references, library)
        projection_service = ProductionProjectionService(
            caps,
            references,
            library=library,
            readiness=service,
        )
    else:
        service = projection_service.readiness

    install_cap_editor_contract_refactoring()
    install_structured_cap_editor()
    install_cap_workspace_refactoring(cap_manager, projection_service)
    install_modernise_cap_action(cap_manager)

    cap_manager.search_input.textChanged.disconnect()
    cap_manager.search_input.textChanged.connect(cap_manager.refresh)
    cap_manager.status_filter.currentIndexChanged.disconnect()
    cap_manager.status_filter.currentIndexChanged.connect(cap_manager.refresh)
    cap_manager.refresh_button.clicked.disconnect()
    cap_manager.refresh_button.clicked.connect(cap_manager.refresh)

    button = QPushButton("Readiness")
    button.setObjectName("capReadinessButton")
    button.setToolTip("Evaluate deterministic CAP production readiness")

    def show_readiness() -> None:
        selected = cap_manager._selected_asset_id()
        if selected is None:
            QMessageBox.information(cap_manager, "CAP Readiness", "Select a CAP first.")
            return
        try:
            report = service.evaluate(selected)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.critical(cap_manager, "CAP Readiness", str(exc))
            return
        CAPReadinessDialog(report, cap_manager).exec()

    button.clicked.connect(show_readiness)
    top_layout = cap_manager.layout()
    if top_layout is None or top_layout.count() == 0:
        return None
    controls = top_layout.itemAt(0).layout()
    if controls is None:
        return None
    controls.insertWidget(max(0, controls.count() - 3), button)
    cap_manager.readiness_service = service
    cap_manager.readiness_button = button
    cap_manager.production_projection_service = projection_service
    return button
