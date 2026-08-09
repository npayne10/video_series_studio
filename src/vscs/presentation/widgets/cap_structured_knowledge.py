"""Structured CAP knowledge editor and AI-assisted migration UI."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps import CAPStructuredKnowledgeService, StructuredKnowledgeError
from vscs.domain.caps import (
    CanonicalConstraintKind,
    KnowledgeAuthority,
    PersistedCanonicalConstraint,
    PersistedCanonicalFact,
    PersistedFunctionalCapability,
    StructuredCAPKnowledge,
)


def _add_row(table: QTableWidget, values: tuple[str, ...]) -> None:
    row = table.rowCount()
    table.insertRow(row)
    for column, value in enumerate(values):
        table.setItem(row, column, QTableWidgetItem(value))


def _remove_selected(table: QTableWidget) -> None:
    rows = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
    for row in rows:
        table.removeRow(row)


def _text(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    return "" if item is None else item.text().strip()


def _terms(text: str) -> tuple[str, ...]:
    normalized = text.replace(",", "\n")
    return tuple(dict.fromkeys(item.strip() for item in normalized.splitlines() if item.strip()))


class StructuredKnowledgeProposalDialog(QDialog):
    """Review an AI-generated structured proposal before placing it in the editor."""

    def __init__(self, knowledge: StructuredCAPKnowledge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.knowledge = knowledge
        self.setWindowTitle("Structured CAP Knowledge Proposal")
        self.resize(760, 520)
        summary = QLabel(
            "AI proposal only — nothing is persisted until you accept this proposal and save the CAP.\n\n"
            f"Facts: {len(knowledge.facts)}\n"
            f"Capabilities: {len(knowledge.functional_identity)}\n"
            f"Constraints: {len(knowledge.constraints)}\n"
            f"Semantic tags: {len(knowledge.semantic_tags)}"
        )
        summary.setWordWrap(True)
        preview = QTableWidget(0, 3)
        preview.setHorizontalHeaderLabels(("Type", "Value", "Authority"))
        for fact in knowledge.facts:
            _add_row(preview, ("Fact", f"{fact.key}: {fact.value}", fact.authority.value))
        for capability in knowledge.functional_identity:
            _add_row(
                preview,
                ("Capability", capability.capability, capability.authority.value),
            )
        for constraint in knowledge.constraints:
            _add_row(preview, (constraint.kind.value.title(), constraint.rule, constraint.authority.value))
        preview.horizontalHeader().setStretchLastSection(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use Proposal")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(summary)
        layout.addWidget(preview, 1)
        layout.addWidget(buttons)


def install_structured_cap_editor() -> None:
    """Extend CAPEditorDialog with machine-readable production knowledge fields."""
    from vscs.presentation.widgets import cap_manager

    editor = cap_manager.CAPEditorDialog
    if getattr(editor, "_phase_19_1_structured_installed", False):
        return

    original_init = editor.__init__
    original_create_value = editor.create_value
    original_update_value = editor.update_value

    def structured_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)

        self.structured_tabs = QTabWidget()
        self.structured_tabs.setObjectName("capStructuredKnowledgeTabs")
        self.structured_tabs.setMinimumHeight(230)

        self.facts_table = QTableWidget(0, 4)
        self.facts_table.setHorizontalHeaderLabels(("Key", "Value", "Unit", "Authority"))
        facts_page = _table_page(self.facts_table, ("New Fact", "", "", "approved"))
        self.structured_tabs.addTab(facts_page, "Facts")

        self.capabilities_table = QTableWidget(0, 3)
        self.capabilities_table.setHorizontalHeaderLabels(("Capability", "Description", "Authority"))
        capabilities_page = _table_page(
            self.capabilities_table,
            ("New Capability", "", "approved"),
        )
        self.structured_tabs.addTab(capabilities_page, "Capabilities")

        self.constraints_table = QTableWidget(0, 4)
        self.constraints_table.setHorizontalHeaderLabels(("Kind", "Rule", "Rationale", "Authority"))
        constraints_page = _table_page(
            self.constraints_table,
            ("required", "New Constraint", "", "approved"),
        )
        self.structured_tabs.addTab(constraints_page, "Constraints")

        classification_page = QWidget()
        classification_form = QFormLayout(classification_page)
        self.semantic_tags_input = QLineEdit()
        self.semantic_tags_input.setPlaceholderText("Comma-separated production tags")
        self.production_classifications_input = QLineEdit()
        self.production_classifications_input.setPlaceholderText("Comma-separated classifications")
        self.behaviour_references_input = QLineEdit()
        self.behaviour_references_input.setPlaceholderText("Comma-separated behaviour contract IDs")
        self.production_metadata_table = QTableWidget(0, 2)
        self.production_metadata_table.setHorizontalHeaderLabels(("Key", "Value"))
        metadata_buttons = QHBoxLayout()
        add_metadata = QPushButton("Add Metadata")
        remove_metadata = QPushButton("Remove Selected")
        add_metadata.clicked.connect(lambda: _add_row(self.production_metadata_table, ("key", "value")))
        remove_metadata.clicked.connect(lambda: _remove_selected(self.production_metadata_table))
        metadata_buttons.addWidget(add_metadata)
        metadata_buttons.addWidget(remove_metadata)
        metadata_buttons.addStretch(1)
        metadata_box = QVBoxLayout()
        metadata_box.addWidget(self.production_metadata_table)
        metadata_box.addLayout(metadata_buttons)
        classification_form.addRow("Semantic tags", self.semantic_tags_input)
        classification_form.addRow("Production classifications", self.production_classifications_input)
        classification_form.addRow("Behaviour references", self.behaviour_references_input)
        classification_form.addRow("Production metadata", metadata_box)
        self.structured_tabs.addTab(classification_page, "Classification")

        heading = QLabel(
            "Structured Production Knowledge — machine-readable facts, capabilities and constraints. "
            "Human-entered values are saved as Approved."
        )
        heading.setWordWrap(True)
        heading.setObjectName("capStructuredKnowledgeGuidance")

        self.propose_structured_button = QPushButton("Propose Structured Knowledge…")
        self.propose_structured_button.setObjectName("proposeStructuredKnowledgeButton")
        parent = self.parent()
        generator = getattr(parent, "generator", None)
        self._structured_service = (
            CAPStructuredKnowledgeService(self.caps, generator.provider)
            if generator is not None
            else None
        )
        self.propose_structured_button.setEnabled(
            self.profile is not None and self._structured_service is not None
        )
        self.propose_structured_button.clicked.connect(lambda: _propose(self))

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(heading)
        container_layout.addWidget(self.structured_tabs)
        container_layout.addWidget(self.propose_structured_button)

        form = self.layout().itemAt(1 if self.layout().count() > 2 else 0).layout()
        if not isinstance(form, QFormLayout):
            for index in range(self.layout().count()):
                candidate = self.layout().itemAt(index).layout()
                if isinstance(candidate, QFormLayout):
                    form = candidate
                    break
        if isinstance(form, QFormLayout):
            form.insertRow(max(0, form.rowCount() - 1), "Structured Production Knowledge", container)
        else:
            self.layout().insertWidget(max(0, self.layout().count() - 1), container)

        if self.profile is not None:
            _load_knowledge(self, self.profile)

    def structured_create_value(self: Any):
        value = original_create_value(self)
        knowledge = _read_knowledge(self)
        return value.model_copy(
            update={
                "structured_schema_version": knowledge.schema_version,
                "facts": knowledge.facts,
                "functional_identity": knowledge.functional_identity,
                "constraints": knowledge.constraints,
                "semantic_tags": knowledge.semantic_tags,
                "production_classifications": knowledge.production_classifications,
                "behaviour_references": knowledge.behaviour_references,
                "production_metadata": knowledge.production_metadata,
            }
        )

    def structured_update_value(self: Any):
        value = original_update_value(self)
        knowledge = _read_knowledge(self)
        return value.model_copy(
            update={
                "structured_schema_version": knowledge.schema_version,
                "facts": knowledge.facts,
                "functional_identity": knowledge.functional_identity,
                "constraints": knowledge.constraints,
                "semantic_tags": knowledge.semantic_tags,
                "production_classifications": knowledge.production_classifications,
                "behaviour_references": knowledge.behaviour_references,
                "production_metadata": knowledge.production_metadata,
            }
        )

    editor.__init__ = structured_init
    editor.create_value = structured_create_value
    editor.update_value = structured_update_value
    editor._phase_19_1_structured_installed = True


def _table_page(table: QTableWidget, defaults: tuple[str, ...]) -> QWidget:
    table.horizontalHeader().setStretchLastSection(True)
    add = QPushButton("Add")
    remove = QPushButton("Remove Selected")
    add.clicked.connect(lambda: _add_row(table, defaults))
    remove.clicked.connect(lambda: _remove_selected(table))
    buttons = QHBoxLayout()
    buttons.addWidget(add)
    buttons.addWidget(remove)
    buttons.addStretch(1)
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.addWidget(table)
    layout.addLayout(buttons)
    return page


def _read_knowledge(dialog: Any) -> StructuredCAPKnowledge:
    facts = tuple(
        PersistedCanonicalFact(
            key=_text(dialog.facts_table, row, 0),
            value=_text(dialog.facts_table, row, 1),
            unit=_text(dialog.facts_table, row, 2) or None,
            source="Human CAP editor",
            authority=KnowledgeAuthority.APPROVED,
        )
        for row in range(dialog.facts_table.rowCount())
        if _text(dialog.facts_table, row, 0) and _text(dialog.facts_table, row, 1)
    )
    capabilities = tuple(
        PersistedFunctionalCapability(
            capability=_text(dialog.capabilities_table, row, 0),
            description=_text(dialog.capabilities_table, row, 1),
            source="Human CAP editor",
            authority=KnowledgeAuthority.APPROVED,
        )
        for row in range(dialog.capabilities_table.rowCount())
        if _text(dialog.capabilities_table, row, 0)
    )
    constraints = tuple(
        PersistedCanonicalConstraint(
            kind=CanonicalConstraintKind(_text(dialog.constraints_table, row, 0).lower()),
            rule=_text(dialog.constraints_table, row, 1),
            rationale=_text(dialog.constraints_table, row, 2),
            source="Human CAP editor",
            authority=KnowledgeAuthority.APPROVED,
        )
        for row in range(dialog.constraints_table.rowCount())
        if _text(dialog.constraints_table, row, 1)
    )
    metadata = {
        _text(dialog.production_metadata_table, row, 0): _text(
            dialog.production_metadata_table, row, 1
        )
        for row in range(dialog.production_metadata_table.rowCount())
        if _text(dialog.production_metadata_table, row, 0)
        and _text(dialog.production_metadata_table, row, 1)
    }
    return StructuredCAPKnowledge(
        facts=facts,
        functional_identity=capabilities,
        constraints=constraints,
        semantic_tags=_terms(dialog.semantic_tags_input.text()),
        production_classifications=_terms(dialog.production_classifications_input.text()),
        behaviour_references=_terms(dialog.behaviour_references_input.text()),
        production_metadata=metadata,
    )


def _load_knowledge(dialog: Any, profile: Any) -> None:
    dialog.facts_table.setRowCount(0)
    for fact in profile.facts:
        _add_row(
            dialog.facts_table,
            (fact.key, fact.value, fact.unit or "", fact.authority.value),
        )
    dialog.capabilities_table.setRowCount(0)
    for capability in profile.functional_identity:
        _add_row(
            dialog.capabilities_table,
            (capability.capability, capability.description, capability.authority.value),
        )
    dialog.constraints_table.setRowCount(0)
    for constraint in profile.constraints:
        _add_row(
            dialog.constraints_table,
            (
                constraint.kind.value,
                constraint.rule,
                constraint.rationale,
                constraint.authority.value,
            ),
        )
    dialog.semantic_tags_input.setText(", ".join(profile.semantic_tags))
    dialog.production_classifications_input.setText(
        ", ".join(profile.production_classifications)
    )
    dialog.behaviour_references_input.setText(", ".join(profile.behaviour_references))
    dialog.production_metadata_table.setRowCount(0)
    for key, value in sorted(profile.production_metadata.items()):
        _add_row(dialog.production_metadata_table, (key, value))


def _apply_to_editor(dialog: Any, knowledge: StructuredCAPKnowledge) -> None:
    class Profile:
        facts = knowledge.facts
        functional_identity = knowledge.functional_identity
        constraints = knowledge.constraints
        semantic_tags = knowledge.semantic_tags
        production_classifications = knowledge.production_classifications
        behaviour_references = knowledge.behaviour_references
        production_metadata = knowledge.production_metadata

    _load_knowledge(dialog, Profile())


def _propose(dialog: Any) -> None:
    if dialog.profile is None or dialog._structured_service is None:
        return
    try:
        proposal = dialog._structured_service.propose(dialog.profile.asset_id)
    except (StructuredKnowledgeError, RuntimeError, ValueError) as exc:
        QMessageBox.critical(dialog, "Structured CAP Knowledge", str(exc))
        return
    review = StructuredKnowledgeProposalDialog(proposal.knowledge, dialog)
    if review.exec():
        _apply_to_editor(dialog, proposal.knowledge)
