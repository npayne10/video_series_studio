"""Episode Assembly workspace foundation: read-only governed timeline inspection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QScrollArea,
    QSplitter,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.episode_draft_selection import (
    approval_evidence_reference,
    approved_media_choices,
    build_partial_draft,
    publish_partial_draft,
)
from vscs.application.episode_evidence_inventory import reconcile_shot_evidence
from vscs.application.episode_planning_snapshot import (
    JsonPlanningSnapshotRepository,
    build_planning_snapshot,
    resolve_current_planning_snapshot,
)
from vscs.application.episode_shot_set_resolver import (
    EpisodeShotSet,
    reconcile_episode_coverage,
    resolve_episode_shots,
)
from vscs.application.episode_timeline_revision_management import (
    prepare_successor_revision,
    publish_successor_revision,
)
from vscs.application.episode_video_frame_inspection import read_approved_video_frames
from vscs.application.generated_media import GeneratedMediaPersistenceService
from vscs.infrastructure.assembly_replacement_decisions import (
    JsonReplacementDecisionRepository,
    ReplacementDecision,
    ReplacementDecisionError,
)
from vscs.infrastructure.assembly_timeline import (
    AssemblyEvidenceError,
    AssemblyMediaEvidenceValidator,
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
        verified_assembly_scope: Callable[[str, tuple[str, ...]], Any | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("episodeAssemblyWorkspace")
        self._project_directory = project_directory
        self._authority_services = authority_services
        self._verified_assembly_scope = verified_assembly_scope
        layout = QVBoxLayout(self)
        heading = QLabel("Episode Assembly", self)
        heading.setObjectName("episodeAssemblyHeading")
        layout.addWidget(heading)
        layout.addWidget(
            QLabel(
                "Shot Set Readiness & Completion — authoritative planning integration pending", self
            )
        )
        self.assembly_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.assembly_splitter.setObjectName("episodeAssemblyResponsiveSplitter")
        self.assembly_splitter.setChildrenCollapsible(False)
        self.coverage_scroll = QScrollArea(self.assembly_splitter)
        self.coverage_scroll.setObjectName("episodeAssemblyCoverageScroll")
        self.coverage_scroll.setWidgetResizable(True)
        self.coverage_panel = QWidget()
        coverage_layout = QVBoxLayout(self.coverage_panel)
        self.coverage_scroll.setWidget(self.coverage_panel)
        self.timeline_scroll = QScrollArea(self.assembly_splitter)
        self.timeline_scroll.setObjectName("episodeAssemblyTimelineScroll")
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_panel = QWidget()
        timeline_layout = QVBoxLayout(self.timeline_panel)
        self.timeline_scroll.setWidget(self.timeline_panel)
        self.assembly_splitter.addWidget(self.coverage_scroll)
        self.assembly_splitter.addWidget(self.timeline_scroll)
        self.assembly_splitter.setStretchFactor(0, 1)
        self.assembly_splitter.setStretchFactor(1, 1)
        self.assembly_splitter.setSizes([1600, 1600])
        layout.addWidget(self.assembly_splitter, 1)
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
        coverage_layout.addWidget(episode_group)
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
        timeline_layout.addWidget(form_group)
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
        timeline_layout.addLayout(actions)
        self.status = QLabel("Open a project and inspect a persisted timeline revision.", self)
        self.status.setObjectName("episodeAssemblyStatus")
        self.status.setWordWrap(True)
        timeline_layout.addWidget(self.status)
        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("episodeAssemblyShotTable")
        self.table.setHorizontalHeaderLabels(
            ["Shot", "Generated Media", "State", "Approval Evidence"]
        )
        self.table.setMinimumHeight(190)
        self.table.setMaximumHeight(380)
        timeline_layout.addWidget(self.table)
        self.coverage_status = QLabel("BLOCKED: Authoritative Episode Shot set not resolved.", self)
        self.coverage_status.setObjectName("episodeCoverageStatus")
        self.coverage_status.setWordWrap(True)
        coverage_layout.addWidget(self.coverage_status)
        self.coverage_table = QTableWidget(0, 5, self)
        self.coverage_table.setObjectName("episodeCoverageMatrix")
        self.coverage_table.setHorizontalHeaderLabels(
            ["Required Shot", "Planning", "Generated Media", "Assembly", "ProductionTask"]
        )
        self.coverage_table.setMinimumHeight(260)
        self.coverage_table.setMaximumHeight(560)
        coverage_layout.addWidget(self.coverage_table)
        self.coverage_table.itemSelectionChanged.connect(self._show_shot_blockers)
        self.draft_media_selector = QComboBox(self)
        self.draft_media_selector.setObjectName("episodeDraftMediaSelector")
        self.draft_media_selector.addItem("Select approved media for highlighted Shot", None)
        coverage_layout.addWidget(self.draft_media_selector)
        self.stage_media_button = QPushButton("Stage Media for Draft (no publication)", self)
        self.stage_media_button.setObjectName("episodeStageDraftMedia")
        self.stage_media_button.clicked.connect(self._stage_selected_media)
        coverage_layout.addWidget(self.stage_media_button)
        self.draft_status = QLabel("No Draft media staged. Completion remains blocked.", self)
        self.draft_status.setObjectName("episodeDraftStagingStatus")
        coverage_layout.addWidget(self.draft_status)
        self._draft_candidates: dict[str, tuple[str, ...]] = {}
        self._staged_media: dict[str, str] = {}
        self.staged_summary = QTableWidget(0, 4, self)
        self.staged_summary.setObjectName("episodeStagedMediaSummary")
        self.staged_summary.setHorizontalHeaderLabels(
            ["Shot", "Approved Generated Media", "Source Frames", "Readiness"]
        )
        self.staged_summary.setMinimumHeight(125)
        self.staged_summary.setMaximumHeight(220)
        coverage_layout.addWidget(self.staged_summary)
        publication = QGroupBox("Governed Draft Publication", self)
        publication_form = QFormLayout(publication)
        self.draft_assembly_id = QLineEdit(self)
        self.draft_assembly_id.setObjectName("draftAssemblyId")
        self.draft_revision_id = QLineEdit(self)
        self.draft_revision_id.setObjectName("draftRevisionId")
        self.draft_in_frame = QSpinBox(self)
        self.draft_in_frame.setObjectName("draftSourceInFrame")
        self.draft_in_frame.setRange(0, 1_000_000)
        self.draft_out_frame = QSpinBox(self)
        self.draft_out_frame.setObjectName("draftSourceOutFrame")
        self.draft_out_frame.setRange(0, 1_000_000)
        self.draft_out_frame.setValue(24)
        publication_form.addRow("Assembly ID", self.draft_assembly_id)
        publication_form.addRow("Revision ID", self.draft_revision_id)
        publication_form.addRow("Source in frame", self.draft_in_frame)
        publication_form.addRow("Source out frame (exclusive)", self.draft_out_frame)
        self.autofill_frames_button = QPushButton("Read Approved Media & Auto-Fill Frames", self)
        self.autofill_frames_button.setObjectName("draftAutoFillFrames")
        self.autofill_frames_button.clicked.connect(self._autofill_source_frames)
        publication_form.addRow(self.autofill_frames_button)
        self.store_frame_range = QPushButton("Set staged Shot frame range", self)
        self.store_frame_range.clicked.connect(self._store_frame_range)
        publication_form.addRow(self.store_frame_range)
        self.publish_draft_button = QPushButton("Review and Publish Immutable Draft", self)
        self.publish_draft_button.setObjectName("publishGovernedDraft")
        self.publish_draft_button.setEnabled(False)
        if verified_assembly_scope is None:
            self.publish_draft_button.setToolTip(
                "Blocked: verified assembly-scope authority is not connected."
            )
        self.publish_draft_button.clicked.connect(self._publish_draft)
        publication_form.addRow(self.publish_draft_button)
        timeline_layout.addWidget(publication)
        self._draft_frames: dict[str, tuple[int, int]] = {}
        successor_group = QGroupBox("Governed Successor Draft Revision", self)
        successor_form = QFormLayout(successor_group)
        self.successor_revision_id = QLineEdit(self)
        self.successor_revision_id.setObjectName("successorRevisionId")
        self.successor_operator = QLineEdit(self)
        self.successor_operator.setObjectName("successorOperator")
        self.successor_reason = QPlainTextEdit(self)
        self.successor_reason.setObjectName("successorReplacementReason")
        self.successor_reason.setMaximumHeight(75)
        successor_form.addRow("New revision ID", self.successor_revision_id)
        successor_form.addRow("Replacement operator", self.successor_operator)
        successor_form.addRow("Replacement justification (if replacing)", self.successor_reason)
        self.successor_preview_button = QPushButton("Preview Successor Differences", self)
        self.successor_preview_button.setObjectName("successorPreview")
        self.successor_preview_button.clicked.connect(self._preview_successor)
        successor_form.addRow(self.successor_preview_button)
        self.successor_comparison = QTableWidget(0, 5, self)
        self.successor_comparison.setObjectName("successorComparison")
        self.successor_comparison.setHorizontalHeaderLabels(
            ["Shot", "Change", "Previous media", "Proposed media", "Source frames"]
        )
        self.successor_comparison.setMinimumHeight(145)
        self.successor_comparison.setMaximumHeight(300)
        successor_form.addRow(self.successor_comparison)
        self.successor_status = QLabel("Select and inspect a persisted Draft predecessor.", self)
        self.successor_status.setWordWrap(True)
        successor_form.addRow(self.successor_status)
        self.successor_publish_button = QPushButton("Confirm & Publish Successor Draft", self)
        self.successor_publish_button.setObjectName("successorPublish")
        self.successor_publish_button.setEnabled(False)
        self.successor_publish_button.clicked.connect(self._publish_successor)
        successor_form.addRow(self.successor_publish_button)
        timeline_layout.addWidget(successor_group)
        self._successor_candidate: Any = None
        self._successor_predecessor_fingerprint: str | None = None

        self.snapshot_operator = QLineEdit(self)
        self.snapshot_operator.setObjectName("planningSnapshotOperator")
        publication_form.addRow("Planning snapshot operator", self.snapshot_operator)
        self.authorize_snapshot = QPushButton("Authorize Immutable Planning Snapshot", self)
        self.authorize_snapshot.setObjectName("authorizePlanningSnapshot")
        self.authorize_snapshot.clicked.connect(self._authorize_planning_snapshot)
        publication_form.addRow(self.authorize_snapshot)
        self._row_blockers: list[tuple[str, ...]] = []
        self.shot_blockers = QPlainTextEdit(self)
        self.shot_blockers.setObjectName("episodeShotBlockerDetails")
        self.shot_blockers.setReadOnly(True)
        self.shot_blockers.setMaximumHeight(120)
        coverage_layout.addWidget(self.shot_blockers)
        self.stages = QLabel(
            "Next governed stages (not yet enabled): Picture Lock → Dialogue & Lip-Sync → "
            "Effects & Transitions → Mastering & Final QC",
            self,
        )
        self.stages.setWordWrap(True)
        timeline_layout.addWidget(self.stages)
        self.assembly_id.textChanged.connect(self._invalidate)
        self.revision_id.textChanged.connect(self._invalidate)
        self.persisted_revisions.currentIndexChanged.connect(self._select_persisted_revision)
        self.episode_selector.currentIndexChanged.connect(self._invalidate)
        self.successor_revision_id.textChanged.connect(self._invalidate_successor_preview)
        self.successor_operator.textChanged.connect(self._invalidate_successor_preview)
        self.successor_reason.textChanged.connect(self._invalidate_successor_preview)
        self._selected_revision: Any = None
        self._resolved_authority: EpisodeShotSet | None = None

    def _invalidate_successor_preview(self, *_args: object) -> None:
        self._successor_candidate = None
        self._successor_predecessor_fingerprint = None
        self.successor_publish_button.setEnabled(False)
        self.successor_comparison.setRowCount(0)

    def _build_successor_candidate(self) -> Any:
        directory = self._project_directory()
        predecessor = self._selected_revision
        episode_id = self.episode_selector.currentData()
        services = self._authority_services() if self._authority_services else None
        if directory is None or predecessor is None or services is None or not episode_id:
            raise ValueError("Open a project, select Episode and inspect a persisted predecessor")
        authority = resolve_episode_shots(episode_id, *services)
        if predecessor.scope.scope_id != episode_id:
            raise ValueError("Selected predecessor belongs to another Episode")
        if not self._staged_media or set(self._draft_frames) != set(self._staged_media):
            raise ValueError("Stage approved media and save source ranges for every change")
        media_service = GeneratedMediaPersistenceService(
            JsonGeneratedMediaRepository(directory / ".vscs" / "generated_media")
        )
        selected = []
        for shot_id, media_id in self._staged_media.items():
            record = media_service.get(media_id)
            if record is None:
                raise ValueError(f"{shot_id}: media record not found")
            approval = approval_evidence_reference(record)
            if approval is None:
                raise ValueError(f"{shot_id}: human approval missing")
            first, last = self._draft_frames[shot_id]
            selected.append((shot_id, record, first, last, approval))
        proposed = build_partial_draft(
            authority,
            predecessor.scope,
            predecessor.assembly_id,
            self.successor_revision_id.text().strip(),
            tuple(selected),
            frame_rate_num=predecessor.frame_rate_num,
            frame_rate_den=predecessor.frame_rate_den,
        )
        existing = {item.shot_id: item for item in predecessor.selections}
        additions = tuple(item for item in proposed.selections if item.shot_id not in existing)
        replacements = tuple(
            item
            for item in proposed.selections
            if item.shot_id in existing
            and item != replace(existing[item.shot_id], sequence_index=item.sequence_index)
        )
        if replacements and (
            not self.successor_operator.text().strip()
            or not self.successor_reason.toPlainText().strip()
        ):
            raise ValueError("Replacement operator and justification are required")
        candidate = prepare_successor_revision(
            predecessor,
            revision_id=self.successor_revision_id.text().strip(),
            authority=authority,
            additions=additions,
            replacements=replacements,
            replacement_reason=self.successor_reason.toPlainText().strip() or None,
        )
        if not additions and not replacements:
            raise ValueError("No changes staged for a successor revision")
        return candidate

    def _preview_successor(self) -> None:
        self._invalidate_successor_preview()
        try:
            candidate = self._build_successor_candidate()
        except (ValueError, RuntimeError, OSError, AssemblyEvidenceError) as exc:
            self.successor_status.setText(f"BLOCKED: {exc}")
            return
        predecessor = self._selected_revision
        old = {item.shot_id: item for item in predecessor.selections}
        self.successor_comparison.setRowCount(0)
        for index, item in enumerate(candidate.selections):
            previous = old.get(item.shot_id)
            kind = (
                "Added"
                if previous is None
                else "Carried"
                if item.generated_media_id == previous.generated_media_id
                and item.source_in_frame == previous.source_in_frame
                and item.source_out_frame == previous.source_out_frame
                else "Replaced"
            )
            values = (
                item.shot_id,
                kind,
                previous.generated_media_id if previous else "—",
                item.generated_media_id,
                f"[{item.source_in_frame}, {item.source_out_frame})",
            )
            self.successor_comparison.insertRow(index)
            for column, value in enumerate(values):
                self.successor_comparison.setItem(index, column, QTableWidgetItem(value))
        self._successor_candidate = candidate
        self._successor_predecessor_fingerprint = predecessor.fingerprint
        self.successor_publish_button.setEnabled(True)
        self.successor_status.setText(
            f"PREVIEW ONLY: {len(candidate.selections)} Shots; "
            "review changes before confirming immutable publication."
        )

    def _publish_successor(self) -> None:
        candidate = self._successor_candidate
        directory = self._project_directory()
        if candidate is None or directory is None or not self._successor_predecessor_fingerprint:
            self.successor_status.setText("BLOCKED: Preview a successor first.")
            return
        try:
            fresh = self._build_successor_candidate()
            if fresh.fingerprint != candidate.fingerprint:
                raise ValueError("Staged changes or operator inputs changed; preview again")
            predecessor = self._selected_revision
            if (
                predecessor is None
                or predecessor.fingerprint != self._successor_predecessor_fingerprint
            ):
                raise ValueError("Predecessor changed; preview again")
            old = {item.shot_id: item for item in predecessor.selections}
            changed = tuple(
                item
                for item in candidate.selections
                if item.shot_id in old
                and item != replace(old[item.shot_id], sequence_index=item.sequence_index)
            )
            if (
                QMessageBox.question(
                    self,
                    "Publish immutable successor?",
                    f"Publish {candidate.assembly_id} / {candidate.revision_id} with "
                    f"{len(candidate.selections)} Shots and {len(changed)} replacements? "
                    "This creates append-only evidence and DOES NOT complete the Episode.",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            services = self._authority_services() if self._authority_services else None
            if services is None:
                raise ValueError("Authoritative planning services unavailable")
            authority = resolve_episode_shots(self.episode_selector.currentData(), *services)
            media_service = GeneratedMediaPersistenceService(
                JsonGeneratedMediaRepository(directory / ".vscs" / "generated_media")
            )
            decisions = JsonReplacementDecisionRepository(directory)
            decision_ids = []
            for item in changed:
                decision = ReplacementDecision(
                    decision_id=f"RD-{uuid4().hex.upper()}",
                    assembly_id=candidate.assembly_id,
                    predecessor_revision_id=predecessor.revision_id,
                    successor_revision_id=candidate.revision_id,
                    predecessor_fingerprint=predecessor.fingerprint,
                    successor_fingerprint=candidate.fingerprint,
                    shot_id=item.shot_id,
                    previous_selection=old[item.shot_id],
                    replacement_selection=item,
                    operator_id=self.successor_operator.text().strip(),
                    justification=self.successor_reason.toPlainText().strip(),
                )
                decisions.create(decision)
                decision_ids.append(decision.decision_id)
            path = publish_successor_revision(
                candidate,
                repository=JsonAssemblyTimelineRepository(directory),
                validator=AssemblyMediaEvidenceValidator(directory, media_service),
                authority=authority,
                expected_predecessor_fingerprint=predecessor.fingerprint,
                decision_repository=decisions,
                replacement_decision_ids=tuple(decision_ids),
            )
        except (
            ValueError,
            RuntimeError,
            OSError,
            AssemblyEvidenceError,
            ReplacementDecisionError,
        ) as exc:
            self.successor_status.setText(f"BLOCKED: Successor publication failed: {exc}")
            return
        self._invalidate_successor_preview()
        self.discover_revisions(select_identity=(candidate.assembly_id, candidate.revision_id))
        self.successor_status.setText(
            f"Published immutable successor at {path}. Episode completion remains blocked."
        )

    def _update_staged_summary(self) -> None:
        self.staged_summary.setRowCount(0)
        for index, (shot_id, media_id) in enumerate(sorted(self._staged_media.items())):
            frames = self._draft_frames.get(shot_id)
            values = (
                shot_id,
                media_id,
                f"[{frames[0]}, {frames[1]})" if frames else "Not recorded",
                "Range recorded" if frames else "Needs source range",
            )
            self.staged_summary.insertRow(index)
            for column, value in enumerate(values):
                self.staged_summary.setItem(index, column, QTableWidgetItem(value))

    def _invalidate(self, *_args: object) -> None:
        self.complete_button.setEnabled(False)
        self.publish_draft_button.setEnabled(False)
        self.table.setRowCount(0)
        self.coverage_table.setRowCount(0)
        self._invalidate_successor_preview()
        self._staged_media.clear()
        self._draft_frames.clear()
        self._update_staged_summary()
        self._draft_candidates.clear()
        self.draft_media_selector.clear()
        self.draft_media_selector.addItem("Select approved media for highlighted Shot", None)
        self.draft_status.setText("No Draft media staged. Completion remains blocked.")
        self._row_blockers = []
        self.shot_blockers.clear()
        self._selected_revision = None
        self._resolved_authority = None
        self.coverage_status.setText("BLOCKED: Episode coverage must be recalculated.")
        self.status.setText("Revision selection changed. Inspect again to view persisted evidence.")

    def _stage_selected_media(self) -> None:
        row = self.coverage_table.currentRow()
        media_id = self.draft_media_selector.currentData()
        if row < 0 or not media_id:
            self.draft_status.setText("BLOCKED: Select a Shot and approved media first.")
            return
        shot_item = self.coverage_table.item(row, 0)
        if shot_item is None:
            return
        shot_id = shot_item.text()
        if media_id not in self._draft_candidates.get(shot_id, ()):
            self.draft_status.setText("BLOCKED: Selected media is not eligible for this Shot.")
            return
        if self._staged_media.get(shot_id) != media_id:
            self._draft_frames.pop(shot_id, None)
        self._invalidate_successor_preview()
        self._staged_media[shot_id] = media_id
        self._update_staged_summary()
        self.draft_status.setText(
            f"{len(self._staged_media)} approved media choice(s) staged in memory. "
            "No Draft published; frame ranges and authoritative scope are still required."
        )

    def _autofill_source_frames(self) -> None:
        """Verify selected media bytes and use actual decoded frame count."""
        row = self.coverage_table.currentRow()
        item = self.coverage_table.item(row, 0) if row >= 0 else None
        shot_id = item.text() if item is not None else ""
        media_id = self._staged_media.get(shot_id)
        directory = self._project_directory()
        if not shot_id or not media_id or directory is None:
            self.draft_status.setText("BLOCKED: Select a staged approved Shot and open project.")
            return
        try:
            repository = JsonGeneratedMediaRepository(directory / ".vscs" / "generated_media")
            media = GeneratedMediaPersistenceService(repository).get(media_id)
            if media is None or media.scope.shot_id != shot_id:
                raise ValueError("Staged media identity no longer matches the Shot")
            details = read_approved_video_frames(directory, media)
            if details.frame_count > self.draft_out_frame.maximum():
                raise ValueError("Source frame count exceeds supported UI frame range")
        except (ValueError, OSError, RuntimeError) as exc:
            self.draft_status.setText(f"BLOCKED: Cannot auto-fill source frames: {exc}")
            return
        self.draft_in_frame.setValue(0)
        self.draft_out_frame.setValue(details.frame_count)
        self._invalidate_successor_preview()
        self._draft_frames.pop(shot_id, None)
        self._update_staged_summary()
        self.draft_status.setText(
            f"Verified {shot_id}: {details.media_id} | {details.relative_path} | "
            f"{details.frame_count} frames at {details.frame_rate} fps "
            f"({details.duration_seconds:.2f} seconds). "
            "Review and click Set staged Shot frame range to save."
        )

    def _store_frame_range(self) -> None:
        row = self.coverage_table.currentRow()
        item = self.coverage_table.item(row, 0) if row >= 0 else None
        shot_id = item.text() if item is not None else ""
        if shot_id not in self._staged_media:
            self.draft_status.setText("BLOCKED: Stage approved media for this Shot first.")
            return
        first, last = self.draft_in_frame.value(), self.draft_out_frame.value()
        if last <= first:
            self.draft_status.setText("BLOCKED: Source out frame must exceed source in frame.")
            return
        self._invalidate_successor_preview()
        self._draft_frames[shot_id] = (first, last)
        self._update_staged_summary()
        self.draft_status.setText(f"Frame range recorded for {shot_id}: [{first}, {last}).")

    def _staged_production_ids(self, directory: Path) -> tuple[str, ...]:
        if not self._staged_media:
            return ()
        service = GeneratedMediaPersistenceService(
            JsonGeneratedMediaRepository(directory / ".vscs" / "generated_media")
        )
        productions = []
        for media_id in self._staged_media.values():
            media = service.get(media_id)
            if media is None:
                raise ValueError("Staged Generated Media record no longer exists")
            productions.append(media.scope.production_id)
        return tuple(productions)

    def _authorize_planning_snapshot(self) -> None:
        directory = self._project_directory()
        episode_id = self.episode_selector.currentData()
        services = self._authority_services() if self._authority_services else None
        if directory is None or not episode_id or services is None:
            self.draft_status.setText("BLOCKED: Open a project and resolve Episode authority.")
            return
        try:
            snapshot = build_planning_snapshot(
                episode_id,
                services,
                self._staged_production_ids(directory),
                self.snapshot_operator.text().strip(),
            )
            if self._resolved_authority is None or (
                snapshot.shot_ids != self._resolved_authority.required_shot_ids
            ):
                raise ValueError("Shot-set order is not the resolved authoritative Episode")
            if (
                QMessageBox.question(
                    self,
                    "Authorize immutable planning snapshot?",
                    "Authorize the current Episode/Scene/Shot planning structure for partial "
                    "Draft assembly? This DOES NOT approve missing Shots or complete the Episode.",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            path = JsonPlanningSnapshotRepository(directory).create(snapshot)
        except (ValueError, RuntimeError, OSError) as exc:
            self.draft_status.setText(f"BLOCKED: Planning snapshot authorization failed: {exc}")
            return
        self.draft_status.setText(
            f"Published planning authority {snapshot.revision_id} at {path}. "
            "No Shot or media approval changed."
        )
        self.publish_draft_button.setEnabled(True)

    def _scope_for_current_draft(self, episode_id: str, authority: EpisodeShotSet) -> Any:
        directory = self._project_directory()
        if directory is None:
            return None
        scope = (
            self._verified_assembly_scope(episode_id, authority.required_shot_ids)
            if self._verified_assembly_scope is not None
            else None
        )
        if scope is not None:
            return scope
        services = self._authority_services() if self._authority_services else None
        if services is None:
            return None
        # A Draft cannot obtain production scope without staged persisted media.
        if not self._staged_media:
            return None
        return resolve_current_planning_snapshot(
            directory,
            episode_id,
            services,
            self._staged_production_ids(directory),
            authority.required_shot_ids,
        )

    def _publish_draft(self) -> None:
        """Publish only after independent authoritative scope and media verification."""
        directory = self._project_directory()
        episode_id = self.episode_selector.currentData()
        if not directory or not episode_id:
            self.draft_status.setText(
                "BLOCKED: Authoritative assembly scope resolver is not connected. No Draft published."
            )
            return
        try:
            services_for_scope = self._authority_services() if self._authority_services else None
            if services_for_scope is None:
                raise ValueError("Episode planning authority unavailable")
            scope_authority = resolve_episode_shots(episode_id, *services_for_scope)
            scope = self._scope_for_current_draft(episode_id, scope_authority)
        except (ValueError, RuntimeError, OSError, AssemblyEvidenceError) as exc:
            self.draft_status.setText(f"BLOCKED: Assembly scope validation failed: {exc}")
            return
        if scope is None:
            self.draft_status.setText("BLOCKED: Verified assembly scope unavailable.")
            return
        if not self._staged_media or set(self._draft_frames) != set(self._staged_media):
            self.draft_status.setText("BLOCKED: Every staged Shot needs a source frame range.")
            return
        if (
            QMessageBox.question(
                self,
                "Publish immutable Draft?",
                "Publish this partial Draft revision? This is append-only and does not complete the Episode.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            services = self._authority_services() if self._authority_services else None
            if services is None:
                raise ValueError("Episode planning authority unavailable")
            authority = resolve_episode_shots(episode_id, *services)
            media_service = GeneratedMediaPersistenceService(
                JsonGeneratedMediaRepository(directory / ".vscs" / "generated_media")
            )
            selected = []
            for shot_id, media_id in self._staged_media.items():
                record = media_service.get(media_id)
                if record is None:
                    raise ValueError(f"{shot_id}: persisted media not found")
                ref = approval_evidence_reference(record)
                if ref is None:
                    raise ValueError(f"{shot_id}: human approval evidence missing")
                first, last = self._draft_frames[shot_id]
                selected.append((shot_id, record, first, last, ref))
            revision = build_partial_draft(
                authority,
                scope,
                self.draft_assembly_id.text().strip(),
                self.draft_revision_id.text().strip(),
                tuple(selected),
            )
            repository = JsonAssemblyTimelineRepository(directory)
            validator = AssemblyMediaEvidenceValidator(directory, media_service)
            path = publish_partial_draft(revision, repository, validator)
        except (ValueError, RuntimeError, OSError, AssemblyEvidenceError) as exc:
            self.draft_status.setText(f"BLOCKED: Draft publication failed: {exc}")
            return
        self.discover_revisions(select_identity=(revision.assembly_id, revision.revision_id))
        self.draft_status.setText(
            f"Published immutable Draft at {path}. Episode completion remains blocked."
        )

    def _show_shot_blockers(self) -> None:
        row = self.coverage_table.currentRow()
        if 0 <= row < len(self._row_blockers):
            details = self._row_blockers[row]
            self.shot_blockers.setPlainText(
                "\n".join(details) if details else "No Shot-specific blockers reported."
            )
        else:
            self.shot_blockers.clear()
        self.draft_media_selector.clear()
        self.draft_media_selector.addItem("Select approved media for highlighted Shot", None)
        item = self.coverage_table.item(row, 0) if row >= 0 else None
        if item is not None:
            for media_id in self._draft_candidates.get(item.text(), ()):
                self.draft_media_selector.addItem(media_id, media_id)

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
        self._draft_candidates = {}
        for choice in approved_media_choices(authority, media):
            if choice.eligible:
                existing = self._draft_candidates.get(choice.shot_id, ())
                self._draft_candidates[choice.shot_id] = (*existing, choice.media_id)
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

        if authority.required_shot_ids:
            try:
                verified_scope = self._scope_for_current_draft(episode_id, authority)
            except (ValueError, RuntimeError, OSError, AssemblyEvidenceError) as exc:
                self.draft_status.setText(f"BLOCKED: Assembly scope validation failed: {exc}")
            else:
                self.publish_draft_button.setEnabled(verified_scope is not None)
                if verified_scope is None:
                    self.draft_status.setText(
                        "BLOCKED: Stage approved media to evaluate new Draft scope. "
                        "Existing persisted revisions remain available for inspection."
                        if not self._staged_media
                        else "BLOCKED: No current verified Assembly Scope for these staged media."
                    )

    def discover_revisions(self, *, select_identity: tuple[str, str] | None = None) -> None:
        """Discover persisted revisions and optionally inspect a specific revision."""
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
            self.persisted_revisions.blockSignals(False)
            self.status.setText(f"BLOCKED: Unable to discover timeline revisions: {exc}")
            return
        for revision in sorted(
            revisions,
            key=lambda item: (item.scope.scope_id, item.assembly_id, item.revision_id),
            reverse=True,
        ):
            self.persisted_revisions.addItem(
                f"{revision.scope.scope_id} | {revision.assembly_id} | {revision.revision_id}",
                (revision.assembly_id, revision.revision_id),
            )
        target = select_identity
        if target is None:
            current_id = (
                self.assembly_id.text().strip(),
                self.revision_id.text().strip(),
            )
            target = current_id if all(current_id) else None
        # Qt can deserialize tuple item data as a list; findData(tuple) then misses it.
        chosen = -1
        if target:
            for index in range(1, self.persisted_revisions.count()):
                identity = self.persisted_revisions.itemData(index)
                if (
                    isinstance(identity, (tuple, list))
                    and len(identity) == 2
                    and tuple(identity) == target
                ):
                    chosen = index
                    break
        self.persisted_revisions.setCurrentIndex(chosen if chosen >= 0 else 0)
        self.persisted_revisions.blockSignals(False)
        if chosen >= 0:
            self._select_persisted_revision(chosen)
        elif not revisions:
            self.status.setText("BLOCKED: No persisted timeline revisions found.")
        else:
            self.status.setText(
                f"{len(revisions)} validated persisted revision(s) available. "
                "Select a revision to inspect."
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
