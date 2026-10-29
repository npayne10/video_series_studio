"""Human review of Story-derived category-specific CAP proposals."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.anchor_placement import AnchorPlacement
from vscs.application.caps.completeness import assess_completeness
from vscs.application.caps.geometry_contract import CAPGeometry
from vscs.application.caps.spatial_proposals import propose_spatial_relationships
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)
from vscs.presentation.dialogs.cap_document_import_dialog import parse_mapping_lines
from vscs.presentation.dialogs.cap_geometry_editor_dialog import CAPGeometryEditorDialog


class StoryCAPSpecificationDialog(QDialog):
    """Review and edit unapproved canonical attributes and reference prompt."""

    def __init__(
        self,
        proposal: StoryCAPProposal,
        parent: QWidget | None = None,
        spatial_candidates: tuple[CAPStructuredSpecification, ...] = (),
    ) -> None:
        super().__init__(parent)
        self.proposal = proposal
        self.spatial_candidates = spatial_candidates
        spec = proposal.specification
        self.setWindowTitle(f"Review Story CAP Draft — {spec.asset_id}")
        self.resize(860, 700)
        self.setMinimumSize(520, 380)
        note = QLabel(
            "Advisory AI proposal only — distinguish story evidence from inferred design. "
            "Save Review & Continue retains edits in the local proposal cache. "
            "Final CAP persistence requires separate confirmation; nothing approves Canon."
        )
        note.setWordWrap(True)
        self.intent = QTextEdit(spec.design_intent)
        self.attributes = QTextEdit(
            "\n".join(f"{key}={value}" for key, value in spec.canonical_attributes.items())
        )
        self.completeness = QLabel()
        self.completeness.setWordWrap(True)
        self.attributes.textChanged.connect(self._update_completeness)
        self.detail_evidence = QTextEdit()
        self.detail_evidence.setReadOnly(True)
        self.detail_evidence.setMaximumHeight(140)
        expansion = proposal.detail_expansion
        if expansion is not None:
            self.detail_evidence.setPlainText(
                "\n".join(
                    f"{candidate.field}: {candidate.authority.value}"
                    + (f" | {candidate.evidence}" if candidate.evidence else "")
                    for candidate in expansion.candidates
                )
            )
        self.variants = QTextEdit()
        self.variants.setPlaceholderText("Optional variant=value1|value2")
        self.prompt = QTextEdit(spec.master_prompt)
        self.rules = QTextEdit("\n".join(spec.continuity_rules))
        self.dependencies = QTextEdit(
            "\n".join(
                "|".join(
                    (
                        item.target_asset_id,
                        item.relation.value,
                        item.anchor,
                        "" if item.minimum_clearance_mm is None else str(item.minimum_clearance_mm),
                        ""
                        if item.placement is None
                        else (f"{item.placement.parent_anchor}>{item.placement.child_anchor}"),
                    )
                )
                for item in spec.dependency_constraints
            )
        )
        self.dependencies.setPlaceholderText(
            "One per line: CAP-PRP-001|contains|forward wall|900|socket>base\n"
            "Fields: asset | relation | spatial anchor | clearance mm | "
            "parent>child named anchors (optional)."
        )
        form_container = QWidget()
        self.geometry_editor = QTextEdit(
            json.dumps(spec.geometry.model_dump(mode="json"), indent=2)
            if spec.geometry is not None
            else ""
        )
        self.geometry_editor.setPlaceholderText(
            'Optional typed geometry JSON: {"frame_id":"room-001", '
            '"origin_mm":{"x":0,"y":0,"z":0}, '
            '"size_mm":{"x":8000,"y":5000,"z":2600},"anchors":[]}'
        )
        form = QFormLayout(form_container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.addRow("Design intent", self.intent)
        form.addRow("Canonical attributes (key=value)", self.attributes)
        form.addRow("Completeness (not approval)", self.completeness)
        form.addRow("Source evidence / design status", self.detail_evidence)
        form.addRow("Allowed variants", self.variants)
        form.addRow("Master reference prompt", self.prompt)
        form.addRow("Continuity (one rule per line)", self.rules)
        self.suggest_dependencies = QPushButton("Analyze Spatial Relationships (Offline)")
        self.suggest_dependencies.clicked.connect(self._analyze_spatial_relationships)
        form.addRow("Offline spatial proposal", self.suggest_dependencies)
        form.addRow("Cross-asset dependencies (reviewed, Draft only)", self.dependencies)
        self.edit_geometry = QPushButton("Edit Geometry (Structured, Draft Only)")
        self.edit_geometry.clicked.connect(self._edit_geometry)
        form.addRow("Structured geometry review", self.edit_geometry)
        form.addRow("Typed geometry (mm, optional JSON Draft)", self.geometry_editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText("Save Review & Continue")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.addWidget(note)
        scroll_layout.addWidget(form_container)
        limitations = QLabel("\n".join(proposal.limitations))
        limitations.setWordWrap(True)
        scroll_layout.addWidget(limitations)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_content)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll_area, 1)
        layout.addWidget(buttons)
        self._reviewed: CAPStructuredSpecification | None = None
        self._update_completeness()

    def _analyze_spatial_relationships(self) -> None:
        """Review only source-backed inverse links, never create dimensions."""
        plan = propose_spatial_relationships(self.proposal.specification, self.spatial_candidates)
        lines = [
            "Offline evidence-based proposals (not Canon):",
            *(f"{item.asset_id}|{item.relation.value} — {item.evidence}" for item in plan.proposed),
            "Unresolved geometry and placement:",
            *(plan.unresolved or ("none",)),
        ]
        if not plan.proposed:
            QMessageBox.information(self, "Offline Spatial Proposal", "\n".join(lines))
            return
        choice = QMessageBox.question(
            self,
            "Review Offline Spatial Proposals",
            "\n".join(lines)
            + "\n\nAppend the proposed relationships to this Draft form? "
            "No dimensions, anchors, clearance or CAP records will be invented.",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        existing = self.dependencies.toPlainText().strip()
        existing_ids = {
            line.split("|", 1)[0].strip().upper()
            for line in existing.splitlines()
            if line.strip()
        }
        proposed_lines = [
            f"{item.asset_id}|{item.relation.value}||"
            for item in plan.proposed
            if item.asset_id not in existing_ids
        ]
        if proposed_lines:
            self.dependencies.setPlainText(
                "\n".join([line for line in (existing, *proposed_lines) if line])
            )

    def _edit_geometry(self) -> None:
        """Apply validated structured geometry only to the in-memory review form."""
        try:
            geometry = (
                CAPGeometry.model_validate_json(self.geometry_editor.toPlainText())
                if self.geometry_editor.toPlainText().strip()
                else None
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Draft Geometry", str(exc))
            return
        editor = CAPGeometryEditorDialog(geometry, self)
        if editor.exec() and editor.result_geometry is not None:
            self.geometry_editor.setPlainText(
                json.dumps(editor.result_geometry.model_dump(mode="json"), indent=2)
            )

    def _update_completeness(self) -> None:
        try:
            attributes = parse_mapping_lines(self.attributes.toPlainText())
            proposal = self.proposal.specification.model_copy(
                update={"canonical_attributes": attributes}
            )
            result = assess_completeness(proposal)
            missing = ", ".join(result.missing) or "none"
            self.completeness.setText(
                f"Missing category fields: {missing}. "
                "Story-suggested values remain unverified until source evidence review. "
                "Saving a Draft does not authorize image generation."
            )
        except ValueError:
            self.completeness.setText("Enter valid key=value canonical attributes.")

    def reviewed(self) -> CAPStructuredSpecification:
        if self._reviewed is None:
            raise ValueError("CAP draft has not been reviewed and accepted")
        return self._reviewed

    def _validate(self) -> None:
        try:
            variants = (
                parse_mapping_lines(self.variants.toPlainText())
                if self.variants.toPlainText().strip()
                else {}
            )
            mapping = {
                key: tuple(value.strip() for value in values.split("|"))
                for key, values in variants.items()
            }
            dependencies = []
            for line in self.dependencies.toPlainText().splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split("|")]
                if len(parts) not in (4, 5):
                    raise ValueError(
                        "Dependencies must use asset|relation|anchor|clearance-mm|parent>child"
                    )
                anchor_pair = parts[4] if len(parts) == 5 else ""
                placement = None
                if anchor_pair:
                    names = [name.strip() for name in anchor_pair.split(">")]
                    if len(names) != 2 or not all(names):
                        raise ValueError("Placement requires parent_anchor>child_anchor")
                    placement = AnchorPlacement(parent_anchor=names[0], child_anchor=names[1])
                dependencies.append(
                    DependencyConstraint(
                        target_asset_id=parts[0],
                        relation=DependencyRelation(parts[1]),
                        anchor=parts[2],
                        minimum_clearance_mm=float(parts[3]) if parts[3] else None,
                        placement=placement,
                    )
                )
            geometry = (
                CAPGeometry.model_validate_json(self.geometry_editor.toPlainText())
                if self.geometry_editor.toPlainText().strip()
                else None
            )
            spec = self.proposal.specification.model_copy(
                update={
                    "design_intent": self.intent.toPlainText(),
                    "canonical_attributes": parse_mapping_lines(self.attributes.toPlainText()),
                    "allowed_variants": mapping,
                    "master_prompt": self.prompt.toPlainText(),
                    "continuity_rules": tuple(
                        item.strip()
                        for item in self.rules.toPlainText().splitlines()
                        if item.strip()
                    ),
                    "dependency_asset_ids": tuple(item.target_asset_id for item in dependencies),
                    "dependency_constraints": tuple(dependencies),
                    "geometry": geometry,
                }
            )
            spec = CAPStructuredSpecification.model_validate(spec.model_dump())
            spec.validate_category_contract()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid CAP Draft", str(exc))
            return
        self._reviewed = spec
        self.accept()
