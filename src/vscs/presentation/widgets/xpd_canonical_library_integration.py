"""Story Workspace UI for Phase 19.5.12 canonical library reuse."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.assets import AssetService, XPDWorkbookError
from vscs.application.automation import CanonicalLibraryImportService, ShotAssetBindingService
from vscs.application.automation.canonical_scope_review import (
    CanonicalScope,
    CanonicalScopeReviewService,
)
from vscs.application.automation.contracts import AutomationProposal
from vscs.application.automation.xpd_binding import (
    CanonicalMatchDiagnostic,
    CanonicalMatchDiagnosticReport,
)


def _table_item(table: QTableWidget, row: int, column: int) -> QTableWidgetItem:
    """Return one populated table item or fail fast on an invalid review UI state."""
    item = table.item(row, column)
    if item is None:
        raise RuntimeError(f"Canonical review table cell ({row}, {column}) is not populated")
    return item


def _review_state(
    proposal: AutomationProposal,
    diagnostic: CanonicalMatchDiagnostic,
    recommendation_scope: CanonicalScope,
) -> str:
    payload = proposal.payload
    scope = str(payload.get("canonical_scope", ""))
    if CanonicalScopeReviewService.is_resolved_canonical(proposal):
        if (
            scope == CanonicalScope.STORY_UNIQUE_CANONICAL.value
            or payload.get("canonical_resolution_source") == "human_created_draft"
        ):
            return "NEW CANONICAL DRAFT"
        return "RESOLVED CANONICAL"
    if scope == CanonicalScope.PROMPT_ELEMENT.value:
        return "PROMPT ELEMENT"
    if scope == CanonicalScope.SCENE_CONTINUITY.value:
        return "SCENE CONTINUITY"
    if scope == CanonicalScope.DEFERRED.value:
        return "DEFERRED"
    if diagnostic.status in {"suggested", "ambiguous"}:
        return "REVIEW EXISTING MATCH"
    if recommendation_scope is CanonicalScope.STORY_UNIQUE_CANONICAL:
        return "NEW CANONICAL CANDIDATE"
    if recommendation_scope is CanonicalScope.PROMPT_ELEMENT:
        return "PROMPT ELEMENT CANDIDATE"
    if recommendation_scope is CanonicalScope.SCENE_CONTINUITY:
        return "SCENE CONTINUITY CANDIDATE"
    return "REVIEW REQUIRED"


def import_xpd_library(parent: QWidget | None, assets: AssetService) -> bool:
    path, _filter = QFileDialog.getOpenFileName(
        parent, "Import Canonical XPD Library", "", "XPD Workbooks (*.xlsx)"
    )
    if not path:
        return False
    service = CanonicalLibraryImportService(assets)
    try:
        preview = service.preview_counts(Path(path))
    except XPDWorkbookError as exc:
        QMessageBox.critical(parent, "XPD Import Error", str(exc))
        return False
    answer = QMessageBox.question(
        parent,
        "Import Canonical XPD Library",
        f"XPD rows: {preview.total_rows}\nNew: {preview.created}\nUpdates: {preview.updated}\nUnchanged: {preview.unchanged}\nConflicts: {preview.conflicts}\nInvalid: {preview.invalid}\n\nImport non-conflicting canonical assets into the current VSCS project?",
    )
    if answer != QMessageBox.StandardButton.Yes:
        return False
    report = service.import_xpd(Path(path))
    QMessageBox.information(
        parent,
        "Canonical XPD Library Imported",
        f"Created: {report.created}\nUpdated: {report.updated}\nUnchanged: {report.unchanged}\nConflicts left for human review: {report.conflicts}\nInvalid: {report.invalid}\n\nNo CAP, Master Reference or production approval was fabricated.",
    )
    return True


def show_match_diagnostics(
    parent: QWidget | None,
    report: CanonicalMatchDiagnosticReport,
    review_service: CanonicalScopeReviewService,
) -> None:
    """Review XPD matches and canonical scope with explicit human decisions."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Canonical XPD Resolution Review")
    dialog.resize(1520, 840)
    layout = QVBoxLayout(dialog)
    summary = QLabel(
        f"Entities: {report.entity_count}    Resolved: {report.resolved_count}    Suggested: {report.suggested_count}    "
        f"Ambiguous: {report.ambiguous_count}    No match: {report.no_match_count}\n"
        "Only persistent identities belong in XPD. Prompt elements and Scene continuity remain outside global canon. "
        "Resolved canonical identities are protected from accidental reclassification."
    )
    summary.setWordWrap(True)
    layout.addWidget(summary)

    table = QTableWidget(len(report.diagnostics), 11, dialog)
    table.setHorizontalHeaderLabels(
        (
            "Story Entity",
            "Category",
            "Review State",
            "Match Status",
            "Scope Decision",
            "Recommended Scope",
            "Current XPD",
            "Suggested XPD",
            "Score",
            "Reason",
            "Alternatives",
        )
    )
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setSortingEnabled(False)
    diagnostics = list(report.diagnostics)
    for row, diagnostic in enumerate(diagnostics):
        best = diagnostic.suggestions[0] if diagnostic.suggestions else None
        alternatives = "; ".join(
            f"{item.asset_name} ({item.score:.2f})" for item in diagnostic.suggestions[1:]
        )
        proposal = review_service.entity_proposal(
            report.story_id, report.source_revision, diagnostic.entity_name
        )
        recommendation = review_service.recommend(proposal)
        scope_decision = str(proposal.payload.get("canonical_scope", ""))
        values = (
            diagnostic.entity_name,
            diagnostic.entity_category,
            _review_state(proposal, diagnostic, recommendation.scope),
            diagnostic.status,
            scope_decision,
            recommendation.scope.value,
            f"{diagnostic.current_asset_id} — {diagnostic.current_asset_name}"
            if diagnostic.current_asset_id
            else "",
            f"{best.asset_id} — {best.asset_name}" if best is not None else "",
            f"{best.score:.2f}" if best is not None else "",
            best.reason if best is not None else recommendation.reason,
            alternatives,
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, column, item)
    table.resizeColumnsToContents()
    table.setSortingEnabled(True)
    layout.addWidget(table, 1)

    guidance = QLabel(
        "Prompt Element: generic shot detail, no persistent identity.  |  "
        "Scene Continuity: preserve locally without XPD growth.  |  "
        "Existing XPD: human-confirm an existing canonical identity.  |  "
        "Create New Canonical: create a Draft Story identity requiring later CAP/Master Reference review."
    )
    guidance.setWordWrap(True)
    layout.addWidget(guidance)

    buttons = QHBoxLayout()
    prompt_button = QPushButton("Mark Prompt Element", dialog)
    scene_button = QPushButton("Mark Scene Continuity", dialog)
    accept_button = QPushButton("Accept Suggested Match", dialog)
    choose_button = QPushButton("Choose Existing Asset…", dialog)
    reject_button = QPushButton("Reject Suggested Match", dialog)
    create_button = QPushButton("Create New Canonical Asset…", dialog)
    defer_button = QPushButton("Defer", dialog)
    review_buttons = (
        prompt_button,
        scene_button,
        accept_button,
        choose_button,
        reject_button,
        create_button,
        defer_button,
    )
    for button in review_buttons:
        buttons.addWidget(button)
    layout.addLayout(buttons)

    def selected() -> tuple[int, CanonicalMatchDiagnostic] | None:
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(dialog, "Canonical Review", "Select a Story entity first.")
            return None
        entity_name = _table_item(table, row, 0).text()
        diagnostic = next(item for item in diagnostics if item.entity_name == entity_name)
        return row, diagnostic

    def update_action_state() -> None:
        row = table.currentRow()
        if row < 0:
            for button in review_buttons:
                button.setEnabled(False)
            return
        entity_name = _table_item(table, row, 0).text()
        diagnostic = next(item for item in diagnostics if item.entity_name == entity_name)
        proposal = review_service.entity_proposal(
            report.story_id, report.source_revision, diagnostic.entity_name
        )
        editable = not review_service.is_resolved_canonical(proposal)
        prompt_button.setEnabled(editable)
        scene_button.setEnabled(editable)
        choose_button.setEnabled(editable)
        create_button.setEnabled(editable)
        defer_button.setEnabled(editable)
        has_suggestion = bool(diagnostic.suggestions)
        accept_button.setEnabled(editable and has_suggestion)
        reject_button.setEnabled(editable and has_suggestion)

    def set_scope(scope: CanonicalScope) -> None:
        choice = selected()
        if choice is None:
            return
        row, diagnostic = choice
        review_service.set_scope(
            story_id=report.story_id,
            source_revision=report.source_revision,
            entity_name=diagnostic.entity_name,
            scope=scope,
        )
        _table_item(table, row, 4).setText(scope.value)
        state = {
            CanonicalScope.PROMPT_ELEMENT: "PROMPT ELEMENT",
            CanonicalScope.SCENE_CONTINUITY: "SCENE CONTINUITY",
            CanonicalScope.DEFERRED: "DEFERRED",
        }.get(scope, "REVIEW REQUIRED")
        _table_item(table, row, 2).setText(state)
        update_action_state()

    def accept_suggested() -> None:
        choice = selected()
        if choice is None:
            return
        row, diagnostic = choice
        if not diagnostic.suggestions:
            QMessageBox.information(
                dialog, "Canonical Review", "This entity has no suggested XPD match."
            )
            return
        candidate = diagnostic.suggestions[0]
        review_service.accept_existing(
            story_id=report.story_id,
            source_revision=report.source_revision,
            entity_name=diagnostic.entity_name,
            asset_id=candidate.asset_id,
        )
        _table_item(table, row, 2).setText("RESOLVED CANONICAL")
        _table_item(table, row, 3).setText("resolved")
        _table_item(table, row, 4).setText(CanonicalScope.PROJECT_CANONICAL.value)
        _table_item(table, row, 6).setText(f"{candidate.asset_id} — {candidate.asset_name}")
        update_action_state()

    def choose_existing() -> None:
        choice = selected()
        if choice is None:
            return
        row, diagnostic = choice
        assets = review_service.compatible_assets(
            story_id=report.story_id,
            source_revision=report.source_revision,
            entity_name=diagnostic.entity_name,
        )
        if not assets:
            QMessageBox.information(
                dialog, "Canonical Review", "No compatible XPD assets are available."
            )
            return
        labels = [f"{asset.asset_id} — {asset.name}" for asset in assets]
        label, ok = QInputDialog.getItem(
            dialog,
            "Choose Existing Canonical Asset",
            f"Canonical identity for {diagnostic.entity_name}:",
            labels,
            0,
            False,
        )
        if not ok:
            return
        asset = assets[labels.index(label)]
        review_service.accept_existing(
            story_id=report.story_id,
            source_revision=report.source_revision,
            entity_name=diagnostic.entity_name,
            asset_id=asset.asset_id,
        )
        _table_item(table, row, 2).setText("RESOLVED CANONICAL")
        _table_item(table, row, 3).setText("resolved")
        _table_item(table, row, 4).setText(CanonicalScope.PROJECT_CANONICAL.value)
        _table_item(table, row, 6).setText(f"{asset.asset_id} — {asset.name}")
        update_action_state()

    def reject_suggested() -> None:
        choice = selected()
        if choice is None:
            return
        row, diagnostic = choice
        if not diagnostic.suggestions:
            QMessageBox.information(
                dialog, "Canonical Review", "This entity has no suggested XPD match."
            )
            return
        candidate = diagnostic.suggestions[0]
        review_service.reject_candidate(
            story_id=report.story_id,
            source_revision=report.source_revision,
            entity_name=diagnostic.entity_name,
            asset_id=candidate.asset_id,
        )
        _table_item(table, row, 2).setText("REVIEW REQUIRED")
        _table_item(table, row, 7).setText("")
        _table_item(table, row, 8).setText("")
        _table_item(table, row, 9).setText(
            "candidate rejected; reopen Review XPD Matches to refresh suggestions"
        )
        update_action_state()

    def create_new() -> None:
        choice = selected()
        if choice is None:
            return
        row, diagnostic = choice
        answer = QMessageBox.question(
            dialog,
            "Create New Canonical Asset",
            f"Create a new Draft canonical identity for '{diagnostic.entity_name}'?\n\n"
            "This adds one XPD asset identity, but does not create a CAP, Master Reference, Ready state, or Production Approval.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        asset = review_service.create_story_canonical(
            story_id=report.story_id,
            source_revision=report.source_revision,
            entity_name=diagnostic.entity_name,
        )
        _table_item(table, row, 2).setText("NEW CANONICAL DRAFT")
        _table_item(table, row, 3).setText("resolved")
        _table_item(table, row, 4).setText(CanonicalScope.STORY_UNIQUE_CANONICAL.value)
        _table_item(table, row, 6).setText(f"{asset.asset_id} — {asset.name}")
        update_action_state()

    prompt_button.clicked.connect(lambda: set_scope(CanonicalScope.PROMPT_ELEMENT))
    scene_button.clicked.connect(lambda: set_scope(CanonicalScope.SCENE_CONTINUITY))
    defer_button.clicked.connect(lambda: set_scope(CanonicalScope.DEFERRED))
    accept_button.clicked.connect(accept_suggested)
    choose_button.clicked.connect(choose_existing)
    reject_button.clicked.connect(reject_suggested)
    create_button.clicked.connect(create_new)
    table.currentCellChanged.connect(lambda *_args: update_action_state())
    update_action_state()

    close_button = QPushButton("Close", dialog)
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)
    dialog.exec()


def binding_summary(service: ShotAssetBindingService, *, story_id: str, revision: str) -> str:
    report = service.bind(story_id=story_id, source_revision=revision)
    return (
        f"Shots inspected: {report.shot_count}\nCanonical Shot/Asset bindings found: {report.binding_count}\n"
        f"Unresolved global-canonical Story entities remaining: {report.unresolved_entity_count}\n\n"
        "Prompt elements and Scene-continuity-only entities are intentionally excluded from global XPD blockers. "
        "No governed Asset Plan was marked Ready or approved."
    )
