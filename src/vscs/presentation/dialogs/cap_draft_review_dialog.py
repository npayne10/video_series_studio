"""Review and moderate an AI-generated CAP Draft Package."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.domain.caps.generation import GeneratedCAPDraft


class CAPDraftReviewDialog(QDialog):
    """Allow a generated CAP package to be edited before it is persisted."""

    def __init__(
        self,
        draft: GeneratedCAPDraft,
        regenerate: Callable[[], GeneratedCAPDraft],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._regenerate = regenerate
        self._draft = draft
        self.setWindowTitle("Review Generated CAP Draft")
        self.setMinimumSize(900, 760)

        notice = QLabel(
            "This content is AI-assisted and is not canon. Review every section, its "
            "supporting facts, unresolved questions, and confidence before creating the Draft CAP."
        )
        notice.setWordWrap(True)

        self.title = QLineEdit()
        self.canonical_description = QTextEdit()
        self.visual_identity = QTextEdit()
        self.production_notes = QTextEdit()
        self.continuity_rules = QTextEdit()
        self.prohibited_variations = QTextEdit()
        self.unresolved_questions = QTextEdit()
        self.source_summary = QTextEdit()
        self.canonical_facts = QTextEdit()
        self.contradictions = QTextEdit()
        self.confidence_summary = QTextEdit()
        for editor in (
            self.canonical_facts,
            self.contradictions,
            self.confidence_summary,
        ):
            editor.setReadOnly(True)

        identity_tab = QWidget()
        identity_form = QFormLayout(identity_tab)
        identity_form.addRow("CAP title", self.title)
        identity_form.addRow("Canonical description", self.canonical_description)
        identity_form.addRow("Visual identity", self.visual_identity)

        production_tab = QWidget()
        production_form = QFormLayout(production_tab)
        production_form.addRow("Production notes", self.production_notes)
        production_form.addRow("Continuity rules (one per line)", self.continuity_rules)
        production_form.addRow(
            "Prohibited variations (one per line)",
            self.prohibited_variations,
        )

        evidence_tab = QWidget()
        evidence_form = QFormLayout(evidence_tab)
        evidence_form.addRow("Extracted canonical facts", self.canonical_facts)
        evidence_form.addRow("Unresolved questions (one per line)", self.unresolved_questions)
        evidence_form.addRow("Source contradictions", self.contradictions)
        evidence_form.addRow("Source summary", self.source_summary)

        confidence_tab = QWidget()
        confidence_form = QFormLayout(confidence_tab)
        confidence_form.addRow("Section confidence", self.confidence_summary)
        confidence_note = QLabel(
            "Confidence is advisory. Low scores indicate sparse, ambiguous, indirect, or visually "
            "incomplete source material and require closer moderator review."
        )
        confidence_note.setWordWrap(True)
        confidence_form.addRow(confidence_note)

        tabs = QTabWidget()
        tabs.addTab(identity_tab, "Canonical Identity")
        tabs.addTab(production_tab, "Production & Continuity")
        tabs.addTab(evidence_tab, "Evidence & Questions")
        tabs.addTab(confidence_tab, "Confidence")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        approve_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        approve_button.setText("Approve and Create Draft")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Reject")
        regenerate_button = QPushButton("Regenerate")
        buttons.addButton(regenerate_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.accepted.connect(self._approve)
        buttons.rejected.connect(self.reject)
        regenerate_button.clicked.connect(self._regenerate_draft)

        layout = QVBoxLayout(self)
        layout.addWidget(notice)
        layout.addWidget(tabs, 1)
        layout.addWidget(buttons)

        self.set_draft(draft)

    def set_draft(self, draft: GeneratedCAPDraft) -> None:
        """Replace all editable fields with a newly generated package."""
        self._draft = draft
        self.title.setText(draft.title)
        self.canonical_description.setPlainText(draft.canonical_description)
        self.visual_identity.setPlainText(draft.visual_identity)
        self.production_notes.setPlainText(draft.production_notes)
        self.continuity_rules.setPlainText("\n".join(draft.continuity_rules))
        self.prohibited_variations.setPlainText("\n".join(draft.prohibited_variations))
        self.unresolved_questions.setPlainText("\n".join(draft.unresolved_questions))
        self.source_summary.setPlainText(draft.source_summary)
        self.canonical_facts.setPlainText(self._format_facts(draft))
        self.contradictions.setPlainText("\n".join(draft.contradictions) or "None identified")
        self.confidence_summary.setPlainText(self._format_confidence(draft))

    def reviewed_draft(self) -> GeneratedCAPDraft:
        """Return a validated draft package containing the moderator's edits."""
        return GeneratedCAPDraft(
            title=self.title.text(),
            canonical_description=self.canonical_description.toPlainText(),
            visual_identity=self.visual_identity.toPlainText(),
            production_notes=self.production_notes.toPlainText(),
            continuity_rules=self._lines(self.continuity_rules),
            prohibited_variations=self._lines(self.prohibited_variations),
            unresolved_questions=self._lines(self.unresolved_questions),
            source_summary=self.source_summary.toPlainText(),
            canonical_facts=self._draft.canonical_facts,
            contradictions=self._draft.contradictions,
            confidence=self._draft.confidence,
        )

    @staticmethod
    def _lines(editor: QTextEdit) -> tuple[str, ...]:
        return tuple(line.strip() for line in editor.toPlainText().splitlines() if line.strip())

    @staticmethod
    def _format_facts(draft: GeneratedCAPDraft) -> str:
        if not draft.canonical_facts:
            return "No canonical facts were extracted."
        return "\n\n".join(
            f"[{fact.confidence:.0%}] {fact.fact}\nEvidence: {fact.evidence}"
            for fact in draft.canonical_facts
        )

    @staticmethod
    def _format_confidence(draft: GeneratedCAPDraft) -> str:
        confidence = draft.confidence
        return (
            f"Canonical description: {confidence.canonical_description:.0%}\n"
            f"Visual identity: {confidence.visual_identity:.0%}\n"
            f"Production notes: {confidence.production_notes:.0%}\n"
            f"Continuity rules: {confidence.continuity_rules:.0%}\n"
            f"Prohibited variations: {confidence.prohibited_variations:.0%}\n\n"
            f"Overall confidence: {confidence.overall:.0%}"
        )

    def _approve(self) -> None:
        try:
            self.reviewed_draft()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid CAP Draft", str(exc))
            return
        self.accept()

    def _regenerate_draft(self) -> None:
        response = QMessageBox.question(
            self,
            "Regenerate CAP Draft",
            "Replace all current edits with a newly generated CAP Draft Package?",
        )
        if response is not QMessageBox.StandardButton.Yes:
            return
        try:
            draft = self._regenerate()
        except (RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, "CAP Generation Error", str(exc))
            return
        self.set_draft(draft)
