"""Operator-only Episode Shot-set completion dialog (Phase 20.18.2.3.7.3).

Readiness never approves Generated Media or completes ProductionTasks.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from vscs.application.generated_media import GeneratedMediaPersistenceService
from vscs.application.shot_set_completion import ShotSetDeclarationError, ShotSetReadiness
from vscs.infrastructure.assembly_timeline import (
    AssemblyEvidenceError,
    AssemblyMediaEvidenceValidator,
    JsonAssemblyTimelineRepository,
)
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository
from vscs.infrastructure.shot_set_completion import (
    GovernedShotSetCompletion,
    JsonShotSetCompletionRepository,
)


class EpisodeShotsCompleteDialog(QDialog):
    """Explicit timeline-backed readiness and operator confirmation UI."""

    def __init__(self, project_directory: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Episode / Video Shots Complete")
        self.setObjectName("episode_shots_complete_dialog")
        self.resize(780, 520)
        self._timeline = JsonAssemblyTimelineRepository(project_directory)
        media = GeneratedMediaPersistenceService(
            JsonGeneratedMediaRepository(
                project_directory / ".vscs" / "generated_media"
            )
        )
        verifier = AssemblyMediaEvidenceValidator(project_directory, media)
        self._governance = GovernedShotSetCompletion(
            verifier, JsonShotSetCompletionRepository(project_directory)
        )
        self._readiness: ShotSetReadiness | None = None
        self._revision = None
        self._expected: tuple[str, ...] = ()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.assembly_id = QLineEdit(self)
        self.assembly_id.setObjectName("shot_set_assembly_id")
        self.revision_id = QLineEdit(self)
        self.revision_id.setObjectName("shot_set_revision_id")
        self.expected_shots = QLineEdit(self)
        self.expected_shots.setObjectName("shot_set_expected_shots")
        self.expected_shots.setPlaceholderText("Approved plan Shot IDs, comma separated")
        self.operator_id = QLineEdit(self)
        self.operator_id.setObjectName("shot_set_operator_id")
        form.addRow("Assembly ID", self.assembly_id)
        form.addRow("Timeline revision", self.revision_id)
        form.addRow("Required Shot IDs (plan order)", self.expected_shots)
        form.addRow("Operator identity", self.operator_id)
        layout.addLayout(form)
        self.status = QLabel(
            "Select a persisted timeline revision and enter the authoritative planned Shot IDs.",
            self,
        )
        self.status.setWordWrap(True)
        self.status.setObjectName("shot_set_readiness_status")
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("shot_set_readiness_table")
        self.table.setHorizontalHeaderLabels(["Shot", "Generated Media", "Status", "Approval"])
        layout.addWidget(self.table)
        controls = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Readiness", self)
        self.refresh_button.setObjectName("shot_set_refresh_readiness")
        self.complete_button = QPushButton("Episode / Video Shots Complete", self)
        self.complete_button.setObjectName("shot_set_declare_complete")
        self.complete_button.setEnabled(False)
        self.complete_button.setToolTip(
            "Awaiting authoritative planned-Shot-set resolution. Manually entered IDs "
            "must not authorize Episode completion."
        )
        self.refresh_button.clicked.connect(self.refresh_readiness)
        self.complete_button.clicked.connect(self.declare_complete)
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.complete_button)
        layout.addLayout(controls)
        for edit in (self.assembly_id, self.revision_id, self.expected_shots, self.operator_id):
            edit.textChanged.connect(self._invalidate)

    def _invalidate(self, *_args: object) -> None:
        self._readiness = None
        self._revision = None
        self.complete_button.setEnabled(False)

    def refresh_readiness(self) -> None:
        self._invalidate()
        self.table.setRowCount(0)
        try:
            revision = self._timeline.get(
                self.assembly_id.text().strip(), self.revision_id.text().strip()
            )
            if revision is None:
                raise AssemblyEvidenceError("Timeline revision not found")
            expected = tuple(
                shot.strip() for shot in self.expected_shots.text().split(",")
                if shot.strip()
            )
            readiness = self._governance.assess(revision, expected)
            self._revision = revision
            self._expected = expected
            self._readiness = readiness
            for index, shot in enumerate(revision.selections):
                self.table.insertRow(index)
                for column, value in enumerate(
                    (shot.shot_id, shot.generated_media_id, shot.media_state,
                     shot.approval_evidence_ref or "Pending")
                ):
                    self.table.setItem(index, column, QTableWidgetItem(value))
            self.status.setText(
                "PREVIEW ONLY: Selected media pass checks, but the required Shot list "
                "has not been verified against authoritative Episode planning."
                if readiness.ready
                else "BLOCKED: " + "; ".join(readiness.blockers)
            )
            self.complete_button.setEnabled(False)
        except (AssemblyEvidenceError, ShotSetDeclarationError, ValueError, OSError) as exc:
            self.status.setText(f"BLOCKED: {exc}")

    def declare_complete(self) -> None:
        readiness = self._readiness
        revision = self._revision
        if not self.complete_button.isEnabled() or readiness is None or revision is None:
            return
        answer = QMessageBox.question(
            self, "Confirm Episode / Video Shots Complete",
            "Declare this selected Shot-set revision complete? This does NOT approve "
            "media, complete ProductionTasks, assemble video, or trigger rendering.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            declaration = self._governance.declare(
                revision, self._expected,
                declaration_id="DECL-" + uuid.uuid4().hex.upper(),
                operator_id=self.operator_id.text().strip(),
                observed_fingerprint=readiness.fingerprint,
            )
        except (AssemblyEvidenceError, ShotSetDeclarationError, ValueError, OSError) as exc:
            self.status.setText(f"BLOCKED: {exc}")
            self.complete_button.setEnabled(False)
            return
        self.status.setText(f"Declared complete: {declaration.declaration_id}")
        self.complete_button.setEnabled(False)
