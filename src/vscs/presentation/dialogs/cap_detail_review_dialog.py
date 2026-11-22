"""Field-by-field review of untrusted CAP design detail proposals."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.completeness import REQUIRED_FIELDS
from vscs.application.caps.design_completion import (
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
    apply_review,
    reviewed_canonical_attributes,
)
from vscs.application.caps.design_quality import DesignQualityIssue
from vscs.application.caps.provider_design_expansion import ProposedDesignField
from vscs.application.caps.story_field_grounding import (
    CAPFieldOrigin,
    CAPFieldProvenance,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification


class CAPDetailReviewDialog(QDialog):
    """Explicit decision for each required field; no writes before confirmation."""

    def __init__(
        self,
        spec: CAPStructuredSpecification,
        *,
        reviewer: str = "Operator",
        suggestions: tuple[ProposedDesignField, ...] = (),
        quality_issues: tuple[DesignQualityIssue, ...] = (),
        field_provenance: tuple[CAPFieldProvenance, ...] = (),
        previous_review: DesignReviewPackage | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.reviewer = reviewer
        if previous_review is not None and (
            previous_review.asset_id != spec.asset_id
            or previous_review.base_fingerprint != spec.fingerprint()
        ):
            raise ValueError("Saved design review is stale; begin a new field review")
        self.previous_review = previous_review
        previous_fields = (
            {field.field: field for field in previous_review.fields}
            if previous_review is not None
            else {}
        )
        self._previous_fields = previous_fields
        proposed = {item.field: item for item in suggestions}
        issue_map: dict[str, list[str]] = {}
        for issue in quality_issues:
            issue_map.setdefault(issue.field, []).append(issue.message)
        self._suggestions = proposed
        self._provenance = {item.field: item for item in field_provenance}
        self.setWindowTitle(f"Review CAP Detail Decisions — {spec.asset_id}")
        self.setMinimumSize(1050, 740)
        self.rows: list[tuple[str, QTextEdit, QComboBox, QTextEdit]] = []
        layout = QVBoxLayout(self)
        note = QLabel(
            "Every required or populated field needs Accept/Edit/Reject/Defer. "
            "Suggested details are not proven Story Canon. "
            "If every field is rejected or deferred, Save retains an immutable "
            "review-only decision record; no CAP specification or approval is created."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.apply_source_suggestions = QPushButton(
            "Apply Story-Source Suggestions (Review Each Field Before Saving)"
        )
        self.apply_source_suggestions.clicked.connect(self._apply_source_suggestions)
        layout.addWidget(self.apply_source_suggestions)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        form.setSpacing(14)
        required_fields = REQUIRED_FIELDS.get(spec.category, ("identity",))
        fields = tuple(dict.fromkeys((*required_fields, *spec.canonical_attributes, *proposed)))
        for field in fields:
            suggestion = proposed.get(field)
            previous = previous_fields.get(field)
            provenance = self._provenance.get(field)
            value = QTextEdit()
            value.setPlainText(
                (previous.final_value or previous.proposed_value)
                if previous is not None
                else spec.canonical_attributes.get(field, "")
                or (suggestion.proposed_value if suggestion is not None else "")
            )
            value.setMinimumHeight(100)
            value.setPlaceholderText("Enter reviewed design detail")
            choice = QComboBox()
            for decision in DetailDecision:
                choice.addItem(decision.value.title(), decision)
            choice.setCurrentIndex(
                choice.findData(previous.decision if previous is not None else DetailDecision.DEFER)
            )
            evidence = QTextEdit()
            evidence.setMinimumHeight(100)
            evidence.setPlaceholderText("Evidence / reason (optional; not auto-verified)")
            comments = []
            if suggestion is not None:
                comments.append(f"AI design proposal: {suggestion.rationale}")
            comments.extend(f"QUALITY REVIEW: {message}" for message in issue_map.get(field, ()))
            evidence.setPlainText(
                previous.evidence if previous is not None else "\n".join(comments)
            )
            row = QHBoxLayout()
            row.addWidget(value, 4)
            row.addWidget(choice, 1)
            row.addWidget(evidence, 3)
            field_block = QVBoxLayout()
            field_block.addLayout(row)
            if provenance is not None:
                quoted_source = (
                    provenance.excerpt
                    if provenance.origin is CAPFieldOrigin.OPERATOR_EDITED
                    else provenance.value
                )
                source_text = (
                    f"{provenance.source_record_id}.{provenance.source_field} "
                    f"[{provenance.source_fingerprint}] — {quoted_source}"
                    if provenance.source_record_id
                    else provenance.value
                )
                trace = QLabel(
                    f"Provenance: {provenance.origin.value}. {provenance.note}\n"
                    f"{source_text}\n"
                    + (
                        f"SHOT-ONLY [{provenance.shot_authority}] "
                        f"{provenance.shot_record_id}.{provenance.shot_field} "
                        f"[{provenance.shot_fingerprint}]: {provenance.shot_excerpt}\n"
                        if provenance.shot_authority
                        else ""
                    )
                    + "Story-source candidate: Accept only after checking. "
                    "AI-only or unresolved: Defer unless independently designed."
                )
                trace.setWordWrap(True)
                field_block.addWidget(trace)
            form.addRow(field, field_block)
            self.rows.append((field, value, choice, evidence))
        scroll.setWidget(body)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_review)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._package: DesignReviewPackage | None = None

    def _apply_source_suggestions(self) -> None:
        """Explicit operator action; never commits or accepts unsupported AI design."""
        for field, _value, choice, _evidence in self.rows:
            provenance = self._provenance.get(field)
            decision = (
                DetailDecision.ACCEPT
                if provenance is not None and provenance.origin is CAPFieldOrigin.STORY_CANDIDATE
                else DetailDecision.DEFER
            )
            choice.setCurrentIndex(choice.findData(decision))

    def reviewed(self) -> DesignReviewPackage:
        if self._package is None:
            raise ValueError("No accepted review")
        return self._package

    def _accept_review(self) -> None:
        try:
            fields = []
            for field, value, choice, evidence in self.rows:
                decision: DetailDecision = choice.currentData()
                text = value.toPlainText().strip()
                previous = self._previous_fields.get(field)
                proposed = self._suggestions.get(field)
                provenance = self._provenance.get(field)
                candidate_value = (
                    previous.proposed_value
                    if previous is not None
                    else self.spec.canonical_attributes.get(field, "")
                    or (proposed.proposed_value if proposed is not None else "")
                )
                if text and text != candidate_value:
                    origin = DetailOrigin.OPERATOR_EDITED
                elif provenance is not None and provenance.origin is CAPFieldOrigin.STORY_CANDIDATE:
                    origin = DetailOrigin.STORY_CANDIDATE
                elif provenance is not None and provenance.origin is CAPFieldOrigin.OPERATOR_EDITED:
                    origin = DetailOrigin.OPERATOR_EDITED
                else:
                    origin = DetailOrigin.DESIGN_PROPOSAL if text else DetailOrigin.UNRESOLVED
                fields.append(
                    DesignFieldReview(
                        field=field,
                        proposed_value=candidate_value,
                        final_value=text
                        if decision in {DetailDecision.ACCEPT, DetailDecision.EDIT}
                        else "",
                        decision=decision,
                        origin=origin,
                        evidence=evidence.toPlainText().strip(),
                        rationale=(
                            previous.rationale
                            if previous is not None
                            else provenance.note
                            if provenance is not None
                            else proposed.rationale
                            if proposed is not None
                            else ""
                        ),
                        source_record_id=(
                            provenance.source_record_id if provenance is not None else ""
                        ),
                        source_field=provenance.source_field if provenance is not None else "",
                        source_fingerprint=(
                            provenance.source_fingerprint if provenance is not None else ""
                        ),
                        source_excerpt=provenance.excerpt if provenance is not None else "",
                        shot_authority=provenance.shot_authority if provenance is not None else "",
                        shot_source_record_id=(
                            provenance.shot_record_id if provenance is not None else ""
                        ),
                        shot_source_fingerprint=(
                            provenance.shot_fingerprint if provenance is not None else ""
                        ),
                        shot_excerpt=provenance.shot_excerpt if provenance is not None else "",
                    )
                )
            package = DesignReviewPackage(
                asset_id=self.spec.asset_id,
                base_fingerprint=self.spec.fingerprint(),
                reviewer=self.reviewer,
                fields=tuple(fields),
            )
            # A complete zero-eligible review is valid *as a decision*, not a CAP.
            if reviewed_canonical_attributes(self.spec, package):
                apply_review(self.spec, package)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Detail Review", str(exc))
            return
        self._package = package
        self.accept()
