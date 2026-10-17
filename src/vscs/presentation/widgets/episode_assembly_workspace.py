"""Episode Assembly workspace foundation: read-only governed timeline inspection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.infrastructure.assembly_timeline import (
    AssemblyEvidenceError,
    JsonAssemblyTimelineRepository,
)


class EpisodeAssemblyWorkspace(QWidget):
    """Inspect persisted episode assembly revisions without declaring completion."""

    def __init__(self, project_directory: Callable[[], Path | None], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("episodeAssemblyWorkspace")
        self._project_directory = project_directory
        layout = QVBoxLayout(self)
        heading = QLabel("Episode Assembly", self)
        heading.setObjectName("episodeAssemblyHeading")
        layout.addWidget(heading)
        layout.addWidget(
            QLabel(
                "Shot Set Readiness & Completion — authoritative planning integration pending", self
            )
        )
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

    def _invalidate(self, *_args: object) -> None:
        self.complete_button.setEnabled(False)
        self.table.setRowCount(0)
        self.status.setText("Revision selection changed. Inspect again to view persisted evidence.")

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
        if not revisions and directory is not None and not self.status.text().startswith("BLOCKED: Unable"):
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
        self.status.setText(
            f"Revision {revision.revision_id}: {len(revision.selections)} selected Shots. "
            "PREVIEW ONLY — the complete approved planned Shot set has not been "
            "resolved from authoritative planning. Completion remains blocked."
        )
