"""Episode Assembly workspace foundation: read-only governed timeline inspection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.episode_evidence_inventory import reconcile_shot_evidence
from vscs.application.episode_shot_set_resolver import (
    EpisodeShotSet,
    reconcile_episode_coverage,
    resolve_episode_shots,
)
from vscs.application.generated_media import GeneratedMediaPersistenceService
from vscs.infrastructure.assembly_timeline import (
    AssemblyEvidenceError,
    JsonAssemblyTimelineRepository,
)
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository


class EpisodeAssemblyWorkspace(QWidget):
    """Inspect persisted episode assembly revisions without declaring completion."""

    def __init__(
        self,
        project_directory: Callable[[], Path | None],
        parent: QWidget | None = None,
        authority_services: Callable[[], tuple[Any, Any, Any, Any] | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("episodeAssemblyWorkspace")
        self._project_directory = project_directory
        self._authority_services = authority_services
        layout = QVBoxLayout(self)
        heading = QLabel("Episode Assembly", self)
        heading.setObjectName("episodeAssemblyHeading")
        layout.addWidget(heading)
        layout.addWidget(
            QLabel(
                "Shot Set Readiness & Completion — authoritative planning integration pending", self
            )
        )
        episode_group = QGroupBox("Authoritative Episode Coverage", self)
        episode_form = QFormLayout(episode_group)
        self.episode_selector = QComboBox(self)
        self.episode_selector.setObjectName("episodeAuthoritySelector")
        self.episode_selector.addItem("Select governed Episode", None)
        episode_form.addRow("Episode", self.episode_selector)
        self.resolve_button = QPushButton("Resolve Episode Shot Set", self)
        self.resolve_button.setObjectName("episodeResolveShotSet")
        self.resolve_button.clicked.connect(self.resolve_coverage)
        episode_form.addRow(self.resolve_button)
        layout.addWidget(episode_group)
        form_group = QGroupBox("Persisted Assembly Timeline Revision", self)
        form = QFormLayout(form_group)
        self.assembly_id = QLineEdit(self)
        self.assembly_id.setObjectName("episodeAssemblyId")
        self.revision_id = QLineEdit(self)
        self.revision_id.setObjectName("episodeRevisionId")
        form.addRow("Assembly ID", self.assembly_id)
        form.addRow("Revision ID", self.revision_id)
        self.persisted_revisions = QComboBox(self)
        self.persisted_revisions.setObjectName("episodePersistedRevisionSelector")
        self.persisted_revisions.addItem("Select persisted timeline revision", None)
        form.addRow("Available revisions", self.persisted_revisions)
        layout.addWidget(form_group)
        actions = QHBoxLayout()
        self.discover_button = QPushButton("Find persisted revisions", self)
        self.discover_button.setObjectName("episodeDiscoverRevisions")
        self.discover_button.clicked.connect(self.discover_revisions)
        actions.addWidget(self.discover_button)
        self.inspect_button = QPushButton("Inspect persisted revision", self)
        self.inspect_button.setObjectName("episodeInspectRevision")
        self.inspect_button.clicked.connect(self.refresh)
        actions.addWidget(self.inspect_button)
        self.complete_button = QPushButton("Episode / Video Shots Complete", self)
        self.complete_button.setObjectName("episodeDeclareComplete")
        self.complete_button.setEnabled(False)
        self.complete_button.setToolTip(
            "Blocked until authoritative planned Shot-set coverage is resolved."
        )
        actions.addWidget(self.complete_button)
        layout.addLayout(actions)
        self.status = QLabel("Open a project and inspect a persisted timeline revision.", self)
        self.status.setObjectName("episodeAssemblyStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("episodeAssemblyShotTable")
        self.table.setHorizontalHeaderLabels(
            ["Shot", "Generated Media", "State", "Approval Evidence"]
        )
        layout.addWidget(self.table)
        self.coverage_status = QLabel("BLOCKED: Authoritative Episode Shot set not resolved.", self)
        self.coverage_status.setObjectName("episodeCoverageStatus")
        self.coverage_status.setWordWrap(True)
        layout.addWidget(self.coverage_status)
        self.coverage_table = QTableWidget(0, 5, self)
        self.coverage_table.setObjectName("episodeCoverageMatrix")
        self.coverage_table.setHorizontalHeaderLabels(
            ["Required Shot", "Planning", "Generated Media", "Assembly", "ProductionTask"]
        )
        layout.addWidget(self.coverage_table)
        self.coverage_table.itemSelectionChanged.connect(self._show_shot_blockers)
        self._row_blockers: list[tuple[str, ...]] = []
        self.shot_blockers = QPlainTextEdit(self)
        self.shot_blockers.setObjectName("episodeShotBlockerDetails")
        self.shot_blockers.setReadOnly(True)
        self.shot_blockers.setMaximumHeight(120)
        layout.addWidget(self.shot_blockers)
        self.stages = QLabel(
            "Next governed stages (not yet enabled): Picture Lock → Dialogue & Lip-Sync → "
            "Effects & Transitions → Mastering & Final QC",
            self,
        )
        self.stages.setWordWrap(True)
        layout.addWidget(self.stages)
        self.assembly_id.textChanged.connect(self._invalidate)
        self.revision_id.textChanged.connect(self._invalidate)
        self.persisted_revisions.currentIndexChanged.connect(self._select_persisted_revision)
        self.episode_selector.currentIndexChanged.connect(self._invalidate)
        self._selected_revision: Any = None
        self._resolved_authority: EpisodeShotSet | None = None

    def _invalidate(self, *_args: object) -> None:
        self.complete_button.setEnabled(False)
        self.table.setRowCount(0)
        self.coverage_table.setRowCount(0)
        self._row_blockers = []
        self.shot_blockers.clear()
        self._selected_revision = None
        self._resolved_authority = None
        self.coverage_status.setText("BLOCKED: Episode coverage must be recalculated.")
        self.status.setText("Revision selection changed. Inspect again to view persisted evidence.")

    def _show_shot_blockers(self) -> None:
        row = self.coverage_table.currentRow()
        if 0 <= row < len(self._row_blockers):
            details = self._row_blockers[row]
            self.shot_blockers.setPlainText(
                "\\n".join(details) if details else "No Shot-specific blockers reported."
            )
        else:
            self.shot_blockers.clear()

    def discover_episodes(self) -> None:
        self.episode_selector.blockSignals(True)
        self.episode_selector.clear()
        self.episode_selector.addItem("Select governed Episode", None)
        services = self._authority_services() if self._authority_services else None
        if services is not None:
            episodes, _scenes, _shots, _reviews = services
            try:
                for episode in episodes.list_plans():
                    self.episode_selector.addItem(
                        f"{episode.episode_id} — {episode.title}", episode.episode_id
                    )
            except (OSError, ValueError, RuntimeError) as exc:
                self.coverage_status.setText(f"BLOCKED: Episode authority unavailable: {exc}")
        self.episode_selector.blockSignals(False)

    def resolve_coverage(self) -> None:
        self.coverage_table.setRowCount(0)
        self.complete_button.setEnabled(False)
        services = self._authority_services() if self._authority_services else None
        episode_id = self.episode_selector.currentData()
        if services is None:
            self.coverage_status.setText("BLOCKED: Governed Episode planning services unavailable.")
            return
        if not episode_id:
            self.coverage_status.setText("BLOCKED: Select an authoritative Episode.")
            return
        try:
            authority = resolve_episode_shots(episode_id, *services)
            self._resolved_authority = authority
            revision = self._selected_revision
            if revision is not None and revision.scope.scope_id != episode_id:
                self.coverage_status.setText(
                    "BLOCKED: Timeline revision belongs to another Episode."
                )
                return
            selections = revision.selections if revision is not None else ()
            coverage = reconcile_episode_coverage(authority, selections)
        except (OSError, ValueError, RuntimeError) as exc:
            self.coverage_status.setText(f"BLOCKED: Episode authority evaluation failed: {exc}")
            return
        directory = self._project_directory()
        try:
            media = (
                GeneratedMediaPersistenceService(
                    JsonGeneratedMediaRepository(directory / ".vscs" / "generated_media")
                ).list_all()
                if directory is not None
                else ()
            )
            media = tuple(item for item in media if item.scope.episode_id == episode_id)
            tasks = (
                JsonProductionTaskRepository(
                    directory / "production" / "scheduling" / "tasks"
                ).list_all()
                if directory is not None
                else ()
            )
            tasks = tuple(task for task in tasks if task.episode_id == episode_id)
        except (OSError, ValueError, RuntimeError) as exc:
            self.coverage_status.setText(f"BLOCKED: Evidence inventory unreadable: {exc}")
            return
        rows = reconcile_shot_evidence(
            authority.required_shot_ids, authority.blockers, selections, media, tasks
        )
        self._row_blockers = [row.blockers for row in rows]
        for index, row in enumerate(rows):
            self.coverage_table.insertRow(index)
            for col, value in enumerate(
                (row.shot_id, row.planning, row.media, row.assembly, row.production_task)
            ):
                self.coverage_table.setItem(index, col, QTableWidgetItem(value))
        planning_blocked = sum(bool(row.planning == "Blocked") for row in rows)
        media_missing = sum(row.media == "No media record" for row in rows)
        qc_pending = sum("QC/approval pending" in row.media for row in rows)
        absent = sum(row.assembly == "Not in timeline" for row in rows)
        self.coverage_status.setText(
            ("BLOCKED: " if coverage.blockers else "PREVIEW: ")
            + f"{len(rows)} required Shots | {planning_blocked} planning blocked | "
            f"{media_missing} without media | {qc_pending} awaiting QC | "
            f"{absent} not in timeline | {len(coverage.blockers)} governance blockers. "
            "Completion remains disabled. Select a Shot row for details."
        )

    def discover_revisions(self) -> None:
        """List only valid persisted timeline records; never infer approval."""
        self._invalidate()
        self.persisted_revisions.blockSignals(True)
        self.persisted_revisions.clear()
        self.persisted_revisions.addItem("Select persisted timeline revision", None)
        directory = self._project_directory()
        try:
            revisions = (
                JsonAssemblyTimelineRepository(directory).list_revisions()
                if directory is not None
                else ()
            )
        except (AssemblyEvidenceError, ValueError, OSError) as exc:
            self.status.setText(f"BLOCKED: Unable to discover timeline revisions: {exc}")
            revisions = ()
        for revision in revisions:
            self.persisted_revisions.addItem(
                f"{revision.scope.scope_id} | {revision.assembly_id} | {revision.revision_id}",
                (revision.assembly_id, revision.revision_id),
            )
        self.persisted_revisions.blockSignals(False)
        if (
            not revisions
            and directory is not None
            and not self.status.text().startswith("BLOCKED: Unable")
        ):
            self.status.setText("BLOCKED: No persisted timeline revisions found.")
        elif revisions:
            self.status.setText(
                f"{len(revisions)} validated persisted revision(s) available. "
                "Select one to inspect; planned Shot-set authority is not yet connected."
            )

    def _select_persisted_revision(self, _index: int) -> None:
        self._invalidate()
        identity = self.persisted_revisions.currentData()
        if identity is None:
            return
        assembly_id, revision_id = identity
        self.assembly_id.setText(assembly_id)
        self.revision_id.setText(revision_id)
        self.refresh()

    def refresh(self) -> None:
        self._invalidate()
        directory = self._project_directory()
        if directory is None:
            self.status.setText("BLOCKED: Open a VSCS project first.")
            return
        assembly = self.assembly_id.text().strip()
        revision_id = self.revision_id.text().strip()
        if not assembly or not revision_id:
            self.status.setText("BLOCKED: Select a persisted Assembly ID and revision.")
            return
        try:
            revision = JsonAssemblyTimelineRepository(directory).get(assembly, revision_id)
        except (AssemblyEvidenceError, ValueError, OSError) as exc:
            self.status.setText(f"BLOCKED: {exc}")
            return
        if revision is None:
            self.status.setText("BLOCKED: Persisted timeline revision not found.")
            return
        self._selected_revision = revision
        for index, shot in enumerate(revision.selections):
            self.table.insertRow(index)
            for col, value in enumerate(
                (
                    shot.shot_id,
                    shot.generated_media_id,
                    shot.media_state,
                    shot.approval_evidence_ref or "Pending",
                )
            ):
                self.table.setItem(index, col, QTableWidgetItem(value))
        if self.episode_selector.currentData():
            self.resolve_coverage()
        self.status.setText(
            f"Revision {revision.revision_id}: {len(revision.selections)} selected Shots. "
            "PREVIEW ONLY — the complete approved planned Shot set has not been "
            "resolved from authoritative planning. Completion remains blocked."
        )
