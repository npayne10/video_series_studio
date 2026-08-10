"""Workspace migration assistant for Phase 19.1 structured CAP knowledge."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QBoxLayout, QMessageBox, QPushButton, QWidget

from vscs.application.caps import StructuredKnowledgeError
from vscs.presentation.widgets.cap_structured_knowledge import (
    StructuredKnowledgeProposalDialog,
)


def install_modernise_cap_action(cap_manager: Any) -> QPushButton | None:
    """Add the governed one-click legacy CAP modernization workflow."""
    existing = getattr(cap_manager, "modernise_cap_button", None)
    if isinstance(existing, QPushButton):
        return existing

    generator = getattr(cap_manager, "generator", None)
    service = getattr(generator, "structured_knowledge", None)
    if service is None:
        return None

    button = QPushButton("Modernise CAP…")
    button.setObjectName("moderniseCAPButton")
    button.setToolTip(
        "Analyse legacy CAP prose, review proposed structured production knowledge, "
        "and persist it only after explicit approval"
    )

    def selected_asset_id() -> str | None:
        selector = getattr(cap_manager, "_selected_asset_id", None)
        if selector is None:
            return None
        selected = selector()
        return selected if isinstance(selected, str) else None

    def update_enabled() -> None:
        asset_id = selected_asset_id()
        if asset_id is None:
            button.setEnabled(False)
            button.setToolTip(
                "Select a CAP to analyse and modernise its structured production knowledge"
            )
            return
        try:
            needs_migration = service.needs_migration(asset_id)
        except (RuntimeError, ValueError):
            button.setEnabled(False)
            return
        button.setEnabled(needs_migration)
        if needs_migration:
            button.setToolTip(
                "Analyse legacy CAP prose, review proposed structured production knowledge, "
                "and persist it only after explicit approval"
            )
        else:
            button.setToolTip("This CAP already contains structured production knowledge")

    def modernise() -> None:
        asset_id = selected_asset_id()
        if asset_id is None:
            QMessageBox.information(cap_manager, "Modernise CAP", "Select a CAP first.")
            return
        try:
            if not service.needs_migration(asset_id):
                QMessageBox.information(
                    cap_manager,
                    "Modernise CAP",
                    "This CAP already contains structured production knowledge.",
                )
                update_enabled()
                return
            proposal = service.propose(asset_id)
        except (StructuredKnowledgeError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(cap_manager, "Modernise CAP", str(exc))
            return

        parent = cap_manager if isinstance(cap_manager, QWidget) else None
        review = StructuredKnowledgeProposalDialog(proposal.knowledge, parent)
        if not review.exec():
            return

        detail = _proposal_summary(proposal)
        answer = QMessageBox.question(
            cap_manager,
            "Approve Structured Production Knowledge",
            (
                "Persist the reviewed proposal as Approved structured production knowledge?\n\n"
                "This is the explicit human approval boundary. AI-proposed knowledge remains "
                "non-authoritative until this action is confirmed."
                f"{detail}"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return

        try:
            approved = service.apply(asset_id, proposal.knowledge)
        except (StructuredKnowledgeError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(cap_manager, "Modernise CAP", str(exc))
            return

        refresh = getattr(cap_manager, "refresh", None)
        if refresh is not None:
            refresh()
        update_enabled()
        QMessageBox.information(
            cap_manager,
            "CAP Modernised",
            (
                f"{asset_id} now contains Approved structured production knowledge.\n\n"
                f"Facts: {len(approved.facts)}\n"
                f"Capabilities: {len(approved.functional_identity)}\n"
                f"Constraints: {len(approved.constraints)}"
            ),
        )

    button.clicked.connect(modernise)
    table = getattr(cap_manager, "table", None)
    if table is not None:
        table.itemSelectionChanged.connect(update_enabled)

    top_layout = cap_manager.layout()
    if top_layout is None or top_layout.count() == 0:
        return None
    first_item = top_layout.itemAt(0)
    if first_item is None:
        return None
    controls = first_item.layout()
    if not isinstance(controls, QBoxLayout):
        return None
    controls.insertWidget(max(0, controls.count() - 3), button)

    cap_manager.modernise_cap_button = button
    cap_manager.structured_knowledge_service = service
    update_enabled()
    return button


def _proposal_summary(proposal: Any) -> str:
    lines: list[str] = []
    if proposal.unresolved_questions:
        lines.append(f"Unresolved questions: {len(proposal.unresolved_questions)}")
    if proposal.contradictions:
        lines.append(f"Source contradictions: {len(proposal.contradictions)}")
    if not lines:
        return ""
    return "\n\n" + "\n".join(lines)
