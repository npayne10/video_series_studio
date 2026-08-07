"""Story Intelligence Workspace and Production Dashboard for Phase 18.2.8."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vscs.application.story import StoryRecord
from vscs.application.story_analysis import (
    StoryAnalysisEngine,
    StoryAnalysisRequest,
    StoryIntelligenceDashboardService,
    StoryIntelligenceDashboardSnapshot,
    StorySourceReader,
    StorySourceReadError,
)


class StoryIntelligenceDashboardDialog(QDialog):
    """Operational review surface for Story Intelligence and production readiness."""

    def __init__(
        self,
        story: StoryRecord,
        engine: StoryAnalysisEngine,
        dashboard: StoryIntelligenceDashboardService,
        parent: QWidget | None = None,
        *,
        review_callback: Callable[[], None] | None = None,
        source_reader: StorySourceReader | None = None,
    ) -> None:
        super().__init__(parent)
        self.story = story
        self.engine = engine
        self.dashboard = dashboard
        self.review_callback = review_callback
        self.source_reader = source_reader or StorySourceReader()
        self.snapshot: StoryIntelligenceDashboardSnapshot | None = None
        self.setObjectName("storyIntelligenceDashboard")
        self.setWindowTitle(f"Story Intelligence — {story.title}")
        self.resize(1440, 860)
        self._build_ui()
        self.refresh_dashboard()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel(f"Story Intelligence — {self.story.title}", self)
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        self.refresh_button = QPushButton("Refresh Dashboard", self)
        self.refresh_button.setObjectName("refreshStoryIntelligence")
        self.refresh_button.clicked.connect(self.refresh_dashboard)
        toolbar.addWidget(self.refresh_button)
        self.review_button = QPushButton("Review AI Entities", self)
        self.review_button.setObjectName("reviewDashboardAIEntities")
        self.review_button.setEnabled(self.review_callback is not None)
        self.review_button.clicked.connect(self._review_entities)
        toolbar.addWidget(self.review_button)
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        toolbar.addWidget(close_button)
        root.addLayout(toolbar)

        self.readiness_label = QLabel("Production readiness not calculated", self)
        self.readiness_label.setObjectName("storyProductionReadiness")
        self.readiness_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        root.addWidget(self.readiness_label)

        metrics = QGridLayout()
        self.analysis_metric = self._metric("Analysis", metrics, 0, 0)
        self.story_metric = self._metric("Story metadata", metrics, 0, 1)
        self.ai_metric = self._metric("AI confidence", metrics, 0, 2)
        self.review_metric = self._metric("Entity review", metrics, 0, 3)
        self.xpd_metric = self._metric("XPD coverage", metrics, 1, 0)
        self.cap_metric = self._metric("CAP readiness", metrics, 1, 1)
        self.graph_metric = self._metric("Knowledge graph", metrics, 1, 2)
        self.production_metric = self._metric("Production gates", metrics, 1, 3)
        root.addLayout(metrics)

        coverage = QHBoxLayout()
        coverage.addWidget(QLabel("XPD coverage", self))
        self.xpd_progress = QProgressBar(self)
        self.xpd_progress.setObjectName("storyXpdCoverage")
        self.xpd_progress.setRange(0, 100)
        coverage.addWidget(self.xpd_progress, 1)
        coverage.addWidget(QLabel("Approved asset CAP readiness", self))
        self.cap_progress = QProgressBar(self)
        self.cap_progress.setObjectName("storyCapReadiness")
        self.cap_progress.setRange(0, 100)
        coverage.addWidget(self.cap_progress, 1)
        root.addLayout(coverage)

        tabs = QTabWidget(self)
        tabs.setObjectName("storyIntelligenceTabs")
        tabs.addTab(self._build_entity_tab(), "Entity Readiness")
        tabs.addTab(self._build_narrative_tab(), "Narrative Intelligence")
        tabs.addTab(self._build_production_tab(), "Production Readiness")
        root.addWidget(tabs, 1)

        self.status_label = QLabel("Not refreshed", self)
        self.status_label.setObjectName("storyIntelligenceStatus")
        root.addWidget(self.status_label)

    def _metric(self, title: str, layout: QGridLayout, row: int, column: int) -> QLabel:
        group = QGroupBox(title, self)
        group_layout = QVBoxLayout(group)
        value = QLabel("—", group)
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet("font-size: 18px; font-weight: 600;")
        group_layout.addWidget(value)
        layout.addWidget(group, row, column)
        return value

    def _build_entity_tab(self) -> QWidget:
        page = QWidget(self)
        root = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.search_edit = QLineEdit(page)
        self.search_edit.setObjectName("storyIntelligenceSearch")
        self.search_edit.setPlaceholderText("Search entity, XPD ID, category or action…")
        self.search_edit.textChanged.connect(self._populate_entities)
        controls.addWidget(self.search_edit, 1)
        self.filter_combo = QComboBox(page)
        self.filter_combo.setObjectName("storyIntelligenceFilter")
        self.filter_combo.addItems(
            (
                "All",
                "Awaiting Review",
                "Approved",
                "Rejected",
                "XPD Matched",
                "CAP Required",
                "Ambiguous Match",
            )
        )
        self.filter_combo.currentTextChanged.connect(self._populate_entities)
        controls.addWidget(self.filter_combo)
        root.addLayout(controls)

        self.entity_table = QTableWidget(0, 8, page)
        self.entity_table.setObjectName("storyIntelligenceEntityTable")
        self.entity_table.setHorizontalHeaderLabels(
            (
                "Status",
                "Type",
                "Name",
                "Confidence",
                "Resolution",
                "XPD Match",
                "CAP Status",
                "Action",
            )
        )
        self.entity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.entity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entity_table.setAlternatingRowColors(True)
        root.addWidget(self.entity_table, 1)
        return page

    def _build_narrative_tab(self) -> QWidget:
        page = QWidget(self)
        root = QVBoxLayout(page)
        self.narrative_view = QPlainTextEdit(page)
        self.narrative_view.setObjectName("storyNarrativeIntelligence")
        self.narrative_view.setReadOnly(True)
        root.addWidget(self.narrative_view)
        return page

    def _build_production_tab(self) -> QWidget:
        page = QWidget(self)
        root = QVBoxLayout(page)
        handoff = QHBoxLayout()
        self.shot_planning_label = QLabel("Shot Planning: Unknown", page)
        self.shot_planning_label.setObjectName("storyShotPlanningReadiness")
        handoff.addWidget(self.shot_planning_label)
        handoff.addStretch(1)
        self.generation_label = QLabel("Generation Assets: Unknown", page)
        self.generation_label.setObjectName("storyGenerationReadiness")
        handoff.addWidget(self.generation_label)
        root.addLayout(handoff)

        root.addWidget(QLabel("Production blockers / actions", page))
        self.readiness_list = QListWidget(page)
        self.readiness_list.setObjectName("storyReadinessReasons")
        root.addWidget(self.readiness_list, 1)
        root.addWidget(QLabel("Analysis diagnostics", page))
        self.diagnostics_list = QListWidget(page)
        self.diagnostics_list.setObjectName("storyIntelligenceDiagnostics")
        root.addWidget(self.diagnostics_list, 1)
        return page

    def refresh_dashboard(self) -> None:
        try:
            source_text = self.source_reader.read(self.story)
        except StorySourceReadError as exc:
            QMessageBox.critical(self, "Story Intelligence", str(exc))
            return
        report = self.engine.analyze(
            StoryAnalysisRequest(
                story_id=self.story.story_id,
                source_text=source_text,
                source_revision=self.story.updated_at or None,
                metadata={"title": self.story.title, "source_path": self.story.source_path},
            )
        )
        self.snapshot = self.dashboard.build(report)
        self._populate_snapshot()

    def _populate_snapshot(self) -> None:
        snapshot = self.snapshot
        if snapshot is None:
            return
        self.readiness_label.setText(
            f"Production readiness: {snapshot.readiness.value.upper()}"
        )
        self.analysis_metric.setText(
            f"{snapshot.analysis_status.value}\n{snapshot.stage_count} stages"
        )
        if snapshot.story_completeness_percent is None:
            self.story_metric.setText("Not available")
        else:
            self.story_metric.setText(
                f"{snapshot.story_completeness_percent}% complete\n"
                f"{len(snapshot.missing_story_metadata)} fields missing"
            )
        self.ai_metric.setText(f"{snapshot.ai_confidence:.0%}")
        self.review_metric.setText(
            f"{snapshot.approved_entities} approved / "
            f"{snapshot.proposed_entities} pending / {snapshot.rejected_entities} rejected"
        )
        self.xpd_metric.setText(
            f"{snapshot.matched_entities} canonical matches\n"
            f"{snapshot.xpd_coverage_percent}% active coverage"
        )
        approved_assets = snapshot.cap_ready_assets + snapshot.cap_required_assets
        self.cap_metric.setText(
            f"{snapshot.cap_ready_assets}/{approved_assets} ready\n"
            f"{snapshot.cap_required_assets} require CAP"
        )
        self.graph_metric.setText(
            f"{snapshot.graph_nodes} nodes\n{snapshot.graph_edges} edges"
        )
        self.production_metric.setText(
            f"Planning: {'ready' if snapshot.ready_for_shot_planning else 'blocked'}\n"
            f"Generation: {'ready' if snapshot.ready_for_generation else 'attention'}"
        )
        self.xpd_progress.setValue(snapshot.xpd_coverage_percent)
        cap_percent = (
            round((snapshot.cap_ready_assets / approved_assets) * 100)
            if approved_assets
            else 100
        )
        self.cap_progress.setValue(cap_percent)
        self._populate_entities()
        self._populate_narrative()
        self._populate_readiness()
        self.status_label.setText(
            f"Dashboard refreshed — {snapshot.entity_total} AI entities, "
            f"{snapshot.unresolved_entities} unresolved"
        )

    def _populate_entities(self) -> None:
        self.entity_table.setRowCount(0)
        if self.snapshot is None:
            return
        query = self.search_edit.text().strip().casefold()
        selected_filter = self.filter_combo.currentText()
        for row in self.snapshot.entity_rows:
            if not self._accept_row(row, selected_filter):
                continue
            haystack = " ".join(
                (
                    row.name,
                    row.category,
                    row.review_status,
                    row.resolution,
                    row.canonical_asset_id or "",
                    row.cap_status,
                    row.action,
                )
            ).casefold()
            if query and query not in haystack:
                continue
            target = self.entity_table.rowCount()
            self.entity_table.insertRow(target)
            values = (
                row.review_status,
                row.category,
                row.name,
                f"{row.confidence:.0%}",
                row.resolution.replace("_", " "),
                row.canonical_asset_id or "New / unresolved",
                row.cap_status,
                row.action,
            )
            for column, value in enumerate(values):
                self.entity_table.setItem(target, column, QTableWidgetItem(value))
        self.entity_table.resizeColumnsToContents()

    @staticmethod
    def _accept_row(row, selected_filter: str) -> bool:
        if selected_filter == "All":
            return True
        if selected_filter == "Awaiting Review":
            return row.review_status == "proposed"
        if selected_filter == "Approved":
            return row.review_status == "approved"
        if selected_filter == "Rejected":
            return row.review_status == "rejected"
        if selected_filter == "XPD Matched":
            return row.canonical_asset_id is not None
        if selected_filter == "CAP Required":
            return row.review_status == "approved" and not row.cap_ready
        if selected_filter == "Ambiguous Match":
            return row.resolution in {"possible_duplicate", "uncertain"}
        return True

    def _populate_narrative(self) -> None:
        snapshot = self.snapshot
        if snapshot is None:
            return
        notes = "\n".join(f"- {note}" for note in snapshot.production_notes) or "None"
        text = (
            f"SUMMARY\n{snapshot.summary or 'Not available'}\n\n"
            f"THEMES\n{', '.join(snapshot.themes) or 'Not available'}\n\n"
            f"TONE\n{', '.join(snapshot.tone) or 'Not available'}\n\n"
            f"SETTING\n{', '.join(snapshot.setting) or 'Not available'}\n\n"
            f"PRODUCTION NOTES\n{notes}\n"
        )
        self.narrative_view.setPlainText(text)

    def _populate_readiness(self) -> None:
        snapshot = self.snapshot
        if snapshot is None:
            return
        self.shot_planning_label.setText(
            "Shot Planning: READY"
            if snapshot.ready_for_shot_planning
            else "Shot Planning: BLOCKED"
        )
        self.generation_label.setText(
            "Generation Assets: READY"
            if snapshot.ready_for_generation
            else "Generation Assets: ATTENTION REQUIRED"
        )
        self.readiness_list.clear()
        if snapshot.readiness_reasons:
            for reason in snapshot.readiness_reasons:
                self.readiness_list.addItem(reason)
        elif snapshot.cap_required_assets:
            self.readiness_list.addItem(
                f"{snapshot.cap_required_assets} approved canonical asset(s) require CAP preparation."
            )
        else:
            self.readiness_list.addItem("No Story Intelligence blockers detected.")
        if snapshot.missing_story_metadata:
            self.readiness_list.addItem(
                "Story metadata incomplete: " + ", ".join(snapshot.missing_story_metadata)
            )
        self.diagnostics_list.clear()
        if snapshot.diagnostics:
            for diagnostic in snapshot.diagnostics:
                self.diagnostics_list.addItem(diagnostic)
        else:
            self.diagnostics_list.addItem("No diagnostics reported.")

    def _review_entities(self) -> None:
        if self.review_callback is None:
            return
        self.review_callback()
        self.refresh_dashboard()
