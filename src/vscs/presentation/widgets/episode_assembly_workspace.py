"""Episode Assembly workspace foundation: read-only governed timeline inspection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
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
        layout.addWidget(form_group)
        actions = QHBoxLayout()
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

    def _invalidate(self, *_args: object) -> None:
        self.complete_button.setEnabled(False)
        self.table.setRowCount(0)
        self.status.setText("Revision selection changed. Inspect again to view persisted evidence.")

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
