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
        self.setWindowTitle("Review Generated CAP Draft")
        self.setMinimumSize(860, 720)

        notice = QLabel(
            "This content is AI-assisted and is not canon. Review every section before "
            "creating the Draft CAP."
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
        evidence_form.addRow("Unresolved questions (one per line)", self.unresolved_questions)
        evidence_form.addRow("Source summary", self.source_summary)

        tabs = QTabWidget()
        tabs.addTab(identity_tab, "Canonical Identity")
        tabs.addTab(production_tab, "Production & Continuity")
        tabs.addTab(evidence_tab, "Sources & Questions")

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
        self.title.setText(draft.title)
        self.canonical_description.setPlainText(draft.canonical_description)
        self.visual_identity.setPlainText(draft.visual_identity)
        self.production_notes.setPlainText(draft.production_notes)
        self.continuity_rules.setPlainText("\n".join(draft.continuity_rules))
        self.prohibited_variations.setPlainText("\n".join(draft.prohibited_variations))
        self.unresolved_questions.setPlainText("\n".join(draft.unresolved_questions))
        self.source_summary.setPlainText(draft.source_summary)

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
        )

    @staticmethod
    def _lines(editor: QTextEdit) -> tuple[str, ...]:
        return tuple(line.strip() for line in editor.toPlainText().splitlines() if line.strip())

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
