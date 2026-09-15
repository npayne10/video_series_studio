"""Human review UI for explicit provider-ready reference suitability authority."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.acpp.reference_roles import (
    ReferenceClass,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
)
from vscs.application.governed_reference_suitability import GovernedReferenceSuitabilityError
from vscs.application.governed_reference_suitability_authoring import (
    GovernedReferenceCandidate,
    GovernedReferenceSuitabilityAuthoringError,
    GovernedReferenceSuitabilityAuthoringService,
    SuitabilityReferenceReview,
    SuitabilityReviewTarget,
)
from vscs.application.production_package import ProductionPackage


@dataclass(slots=True)
class _ReferenceState:
    included: bool
    asset_id: str | None
    semantic_role: str
    category: str
    source_path: str
    canonical_source_id: str | None
    reference_id: str
    label: str
    role: ReferenceRole
    reference_class: ReferenceClass
    subject_type: ReferenceSubjectType
    priority: ReferencePriority
    width: int
    height: int
    checksum: str
    provider_ready: bool
    provider_profiles: str
    framing_type: str
    coverage: str
    required_features_visible: bool
    identity_visible: bool
    full_required_asset_visible: bool
    contains_subjects: str
    contains_props: str
    contains_environments: str
    review_note: str
    custom: bool = False


class GovernedReferenceSuitabilityReviewDialog(QDialog):
    """Author explicit suitability facts and resolve them through governed services."""

    def __init__(
        self,
        authoring: GovernedReferenceSuitabilityAuthoringService,
        package: ProductionPackage,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.authoring = authoring
        self.package = package
        self._states: list[_ReferenceState] = []
        self._current_row = -1
        self._loading_editor = False
        self.setWindowTitle(f"Governed Reference Suitability Review — {package.shot_id}")
        self.resize(1320, 840)
        self._build_ui()
        self._load_states()
        self._populate_table()
        if self._states:
            self.table.selectRow(0)
            self._load_editor(0)
        self._update_action_state()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        heading = QLabel(
            f"<b>{self.package.shot_id}</b> — Production Package {self.package.package_id}",
            self,
        )
        root.addWidget(heading)
        notice = QLabel(
            "Review provider suitability explicitly. Canonical approval alone does not make a "
            "reference provider-ready. This workspace authors suitability authority only; it "
            "does not submit provider execution.",
            self,
        )
        notice.setWordWrap(True)
        root.addWidget(notice)

        target_group = QGroupBox("Target profile", self)
        target_layout = QHBoxLayout(target_group)
        self.target_width = QSpinBox(target_group)
        self.target_width.setRange(1, 16384)
        self.target_width.setValue(1280)
        self.target_height = QSpinBox(target_group)
        self.target_height.setRange(1, 16384)
        self.target_height.setValue(720)
        self.target_profile = QLineEdit("production-video-16x9", target_group)
        self.target_provider = QLineEdit("ltx23-local", target_group)
        self.aspect_tolerance = QDoubleSpinBox(target_group)
        self.aspect_tolerance.setDecimals(3)
        self.aspect_tolerance.setRange(0.001, 0.200)
        self.aspect_tolerance.setSingleStep(0.005)
        self.aspect_tolerance.setValue(0.03)
        for label, widget in (
            ("Width", self.target_width),
            ("Height", self.target_height),
            ("Profile", self.target_profile),
            ("Provider", self.target_provider),
            ("Aspect tolerance", self.aspect_tolerance),
        ):
            target_layout.addWidget(QLabel(label, target_group))
            target_layout.addWidget(widget)
        target_layout.addStretch(1)
        root.addWidget(target_group)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter, 1)

        list_panel = QWidget(splitter)
        list_layout = QVBoxLayout(list_panel)
        self.table = QTableWidget(0, 8, list_panel)
        self.table.setHorizontalHeaderLabels(
            (
                "Use",
                "Asset",
                "Governed Role",
                "Category",
                "Reference File",
                "Dimensions",
                "Provider Ready",
                "Reference Role",
            )
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        list_layout.addWidget(self.table, 1)
        candidate_actions = QHBoxLayout()
        self.add_helper_button = QPushButton("Add Composition / Helper Reference…", list_panel)
        self.remove_helper_button = QPushButton("Remove Added Reference", list_panel)
        candidate_actions.addWidget(self.add_helper_button)
        candidate_actions.addWidget(self.remove_helper_button)
        candidate_actions.addStretch(1)
        list_layout.addLayout(candidate_actions)
        splitter.addWidget(list_panel)

        detail_panel = QWidget(splitter)
        detail_layout = QVBoxLayout(detail_panel)
        self.preview = QLabel("Select a reference to review", detail_panel)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(360, 220)
        self.preview.setMaximumHeight(280)
        self.preview.setStyleSheet("QLabel { border: 1px solid palette(mid); }")
        detail_layout.addWidget(self.preview)

        facts = QGroupBox("Reference facts", detail_panel)
        facts_form = QFormLayout(facts)
        self.path_label = QLabel("—", facts)
        self.path_label.setWordWrap(True)
        self.dimensions_label = QLabel("—", facts)
        self.checksum_label = QLabel("—", facts)
        self.checksum_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        facts_form.addRow("Source", self.path_label)
        facts_form.addRow("Actual dimensions", self.dimensions_label)
        facts_form.addRow("SHA-256", self.checksum_label)
        detail_layout.addWidget(facts)

        editor = QGroupBox("Explicit suitability decision", detail_panel)
        editor_form = QFormLayout(editor)
        self.reference_id = QLineEdit(editor)
        self.label_edit = QLineEdit(editor)
        self.role_combo = self._enum_combo(ReferenceRole, editor)
        self.class_combo = self._enum_combo(ReferenceClass, editor)
        self.subject_combo = self._enum_combo(ReferenceSubjectType, editor)
        self.priority_combo = self._enum_combo(ReferencePriority, editor)
        self.provider_ready = QCheckBox("Explicitly approved as provider-ready", editor)
        self.provider_profiles = QLineEdit(editor)
        self.provider_profiles.setPlaceholderText("production-video-16x9")
        self.framing_type = QLineEdit(editor)
        self.framing_type.setPlaceholderText("e.g. full_body, wide_environment")
        self.coverage = QLineEdit(editor)
        self.coverage.setPlaceholderText("e.g. full_required_asset")
        self.features_visible = QCheckBox("Required features visible", editor)
        self.identity_visible = QCheckBox("Identity-critical detail visible", editor)
        self.full_asset_visible = QCheckBox("Full required asset/environment visible", editor)
        self.contains_subjects = QLineEdit(editor)
        self.contains_subjects.setPlaceholderText("Comma-separated governed asset IDs")
        self.contains_props = QLineEdit(editor)
        self.contains_props.setPlaceholderText("Comma-separated governed asset IDs")
        self.contains_environments = QLineEdit(editor)
        self.contains_environments.setPlaceholderText("Comma-separated governed asset IDs")
        self.review_note = QTextEdit(editor)
        self.review_note.setMaximumHeight(70)
        editor_form.addRow("Reference ID", self.reference_id)
        editor_form.addRow("Label", self.label_edit)
        editor_form.addRow("Role", self.role_combo)
        editor_form.addRow("Reference class", self.class_combo)
        editor_form.addRow("Subject type", self.subject_combo)
        editor_form.addRow("Priority", self.priority_combo)
        editor_form.addRow("Provider readiness", self.provider_ready)
        editor_form.addRow("Provider profiles", self.provider_profiles)
        editor_form.addRow("Framing type", self.framing_type)
        editor_form.addRow("Coverage", self.coverage)
        editor_form.addRow("Visibility", self.features_visible)
        editor_form.addRow("Identity", self.identity_visible)
        editor_form.addRow("Completeness", self.full_asset_visible)
        editor_form.addRow("Contains subjects", self.contains_subjects)
        editor_form.addRow("Contains props", self.contains_props)
        editor_form.addRow("Contains environments", self.contains_environments)
        editor_form.addRow("Review note", self.review_note)
        detail_layout.addWidget(editor, 1)
        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        actions = QHBoxLayout()
        self.save_button = QPushButton("Save Explicit Review", self)
        self.approve_button = QPushButton("Approve Suitability && Persist Plan", self)
        self.cancel_button = QPushButton("Close", self)
        actions.addStretch(1)
        actions.addWidget(self.save_button)
        actions.addWidget(self.approve_button)
        actions.addWidget(self.cancel_button)
        root.addLayout(actions)

        self.table.currentCellChanged.connect(self._selection_changed)
        self.table.itemChanged.connect(self._table_item_changed)
        self.add_helper_button.clicked.connect(self._add_helper)
        self.remove_helper_button.clicked.connect(self._remove_helper)
        self.save_button.clicked.connect(self._save_review)
        self.approve_button.clicked.connect(self._approve)
        self.cancel_button.clicked.connect(self.reject)
        self._connect_editor_changes()

    @staticmethod
    def _enum_combo(enum_type: Any, parent: QWidget) -> QComboBox:
        combo = QComboBox(parent)
        for value in enum_type:
            combo.addItem(value.value, value)
        return combo

    def _connect_editor_changes(self) -> None:
        for widget in (
            self.reference_id,
            self.label_edit,
            self.provider_profiles,
            self.framing_type,
            self.coverage,
            self.contains_subjects,
            self.contains_props,
            self.contains_environments,
        ):
            widget.textChanged.connect(self._editor_changed)
        for combo in (self.role_combo, self.class_combo, self.subject_combo, self.priority_combo):
            combo.currentIndexChanged.connect(self._editor_changed)
        for checkbox in (
            self.provider_ready,
            self.features_visible,
            self.identity_visible,
            self.full_asset_visible,
        ):
            checkbox.toggled.connect(self._editor_changed)
        self.review_note.textChanged.connect(self._editor_changed)

    def _load_states(self) -> None:
        existing = self.authoring.load_review(self.package.shot_id)
        existing_refs = (
            existing.get("references", [])
            if isinstance(existing, dict) and isinstance(existing.get("references"), list)
            else []
        )
        if isinstance(existing, dict):
            target = existing.get("target")
            if isinstance(target, dict):
                self.target_width.setValue(self._positive_int(target.get("width"), 1280))
                self.target_height.setValue(self._positive_int(target.get("height"), 720))
                self.target_profile.setText(
                    str(target.get("profile_id") or "production-video-16x9")
                )
                self.target_provider.setText(str(target.get("provider_id") or "ltx23-local"))
                tolerance = target.get("aspect_tolerance")
                if isinstance(tolerance, int | float) and not isinstance(tolerance, bool):
                    self.aspect_tolerance.setValue(float(tolerance))

        consumed: set[int] = set()
        for candidate in self.authoring.candidates_for_package(self.package):
            match_index, match = self._match_existing(candidate, existing_refs, consumed)
            if match_index is not None:
                consumed.add(match_index)
            self._states.append(self._state_from_candidate(candidate, match))

        for index, value in enumerate(existing_refs):
            if index in consumed or not isinstance(value, dict):
                continue
            self._states.append(self._state_from_existing(value, custom=True))

    def _match_existing(
        self,
        candidate: GovernedReferenceCandidate,
        values: list[object],
        consumed: set[int],
    ) -> tuple[int | None, dict[str, Any] | None]:
        candidate_path = self._path_key(candidate.source_path)
        for index, value in enumerate(values):
            if index in consumed or not isinstance(value, dict):
                continue
            asset_id = str(value.get("asset_id") or "").strip().upper()
            source_path = self._path_key(str(value.get("source_path") or ""))
            if asset_id == candidate.asset_id and source_path == candidate_path:
                return index, value
        return None, None

    def _state_from_candidate(
        self,
        candidate: GovernedReferenceCandidate,
        existing: dict[str, Any] | None,
    ) -> _ReferenceState:
        width, height = self._image_dimensions(candidate.source_path)
        if existing is None:
            role = candidate.suggested_role
            return _ReferenceState(
                included=False,
                asset_id=candidate.asset_id,
                semantic_role=candidate.semantic_role,
                category=candidate.category,
                source_path=candidate.source_path,
                canonical_source_id=candidate.canonical_source_id,
                reference_id=self.authoring.make_reference_id(
                    asset_id=candidate.asset_id,
                    source_path=candidate.source_path,
                    role=role,
                ),
                label=candidate.label,
                role=role,
                reference_class=candidate.suggested_reference_class,
                subject_type=candidate.suggested_subject_type,
                priority=candidate.suggested_priority,
                width=width,
                height=height,
                checksum=candidate.file_checksum or "",
                provider_ready=False,
                provider_profiles="production-video-16x9",
                framing_type="unknown",
                coverage="unknown",
                required_features_visible=False,
                identity_visible=False,
                full_required_asset_visible=False,
                contains_subjects="",
                contains_props="",
                contains_environments="",
                review_note="",
            )
        state = self._state_from_existing(existing, custom=False)
        state.semantic_role = candidate.semantic_role
        state.category = candidate.category
        state.width = width or state.width
        state.height = height or state.height
        state.checksum = candidate.file_checksum or state.checksum
        return state

    def _state_from_existing(self, value: dict[str, Any], *, custom: bool) -> _ReferenceState:
        raw_coverage = value.get("coverage")
        coverage: dict[str, Any] = raw_coverage if isinstance(raw_coverage, dict) else {}
        source_path = str(value.get("source_path") or "")
        actual_width, actual_height = self._image_dimensions(source_path)
        role = self._enum_value(ReferenceRole, value.get("role"), ReferenceRole.BACKGROUND_IDENTITY)
        return _ReferenceState(
            included=True,
            asset_id=(str(value.get("asset_id") or "").strip().upper() or None),
            semantic_role="",
            category="custom" if custom else "",
            source_path=source_path,
            canonical_source_id=(str(value.get("canonical_source_id") or "").strip() or None),
            reference_id=str(value.get("reference_id") or ""),
            label=str(value.get("label") or ""),
            role=role,
            reference_class=self._enum_value(
                ReferenceClass,
                value.get("reference_class"),
                ReferenceClass.SHOT_COMPOSITE if custom else ReferenceClass.CANONICAL_MASTER,
            ),
            subject_type=self._enum_value(
                ReferenceSubjectType,
                value.get("subject_type"),
                ReferenceSubjectType.MULTI_SUBJECT_SCENE if custom else ReferenceSubjectType.OTHER,
            ),
            priority=self._enum_value(
                ReferencePriority,
                value.get("priority"),
                ReferencePriority.REQUIRED,
            ),
            width=actual_width or self._positive_int(value.get("width"), 0),
            height=actual_height or self._positive_int(value.get("height"), 0),
            checksum=self._file_checksum_display(
                source_path, str(value.get("file_checksum") or "")
            ),
            provider_ready=value.get("provider_ready") is True,
            provider_profiles=self._join_values(value.get("provider_profiles")),
            framing_type=str(coverage.get("framing_type") or "unknown"),
            coverage=str(coverage.get("coverage") or "unknown"),
            required_features_visible=coverage.get("required_features_visible") is True,
            identity_visible=coverage.get("identity_visible") is True,
            full_required_asset_visible=coverage.get("full_required_asset_visible") is True,
            contains_subjects=self._join_values(value.get("contains_subjects")),
            contains_props=self._join_values(value.get("contains_props")),
            contains_environments=self._join_values(value.get("contains_environments")),
            review_note=str(value.get("review_note") or ""),
            custom=custom,
        )

    def _populate_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._states))
        for row, state in enumerate(self._states):
            use_item = QTableWidgetItem("")
            use_item.setFlags(use_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            use_item.setCheckState(
                Qt.CheckState.Checked if state.included else Qt.CheckState.Unchecked
            )
            self.table.setItem(row, 0, use_item)
            self.table.setItem(row, 1, QTableWidgetItem(state.asset_id or "—"))
            self.table.setItem(row, 2, QTableWidgetItem(state.semantic_role or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(state.category or "—"))
            self.table.setItem(
                row, 4, QTableWidgetItem(Path(state.source_path).name or state.source_path)
            )
            self.table.setItem(row, 5, QTableWidgetItem(self._dimensions_text(state)))
            self.table.setItem(row, 6, QTableWidgetItem("Yes" if state.provider_ready else "No"))
            self.table.setItem(row, 7, QTableWidgetItem(state.role.value))
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()

    def _selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if current_row < 0 or current_row >= len(self._states):
            return
        self._current_row = current_row
        self._load_editor(current_row)
        self._update_action_state()

    def _table_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0 or not (0 <= item.row() < len(self._states)):
            return
        self._states[item.row()].included = item.checkState() is Qt.CheckState.Checked
        self._update_action_state()

    def _load_editor(self, row: int) -> None:
        state = self._states[row]
        self._loading_editor = True
        try:
            self.path_label.setText(state.source_path)
            self.dimensions_label.setText(self._dimensions_text(state))
            self.checksum_label.setText(state.checksum or "Unavailable")
            self.reference_id.setText(state.reference_id)
            self.label_edit.setText(state.label)
            self._select_enum(self.role_combo, state.role)
            self._select_enum(self.class_combo, state.reference_class)
            self._select_enum(self.subject_combo, state.subject_type)
            self._select_enum(self.priority_combo, state.priority)
            self.provider_ready.setChecked(state.provider_ready)
            self.provider_profiles.setText(state.provider_profiles)
            self.framing_type.setText(state.framing_type)
            self.coverage.setText(state.coverage)
            self.features_visible.setChecked(state.required_features_visible)
            self.identity_visible.setChecked(state.identity_visible)
            self.full_asset_visible.setChecked(state.full_required_asset_visible)
            self.contains_subjects.setText(state.contains_subjects)
            self.contains_props.setText(state.contains_props)
            self.contains_environments.setText(state.contains_environments)
            self.review_note.setPlainText(state.review_note)
            self._show_preview(state.source_path)
        finally:
            self._loading_editor = False

    def _editor_changed(self, *_args: object) -> None:
        if self._loading_editor or not (0 <= self._current_row < len(self._states)):
            return
        state = self._states[self._current_row]
        state.reference_id = self.reference_id.text().strip()
        state.label = self.label_edit.text().strip()
        state.role = self.role_combo.currentData()
        state.reference_class = self.class_combo.currentData()
        state.subject_type = self.subject_combo.currentData()
        state.priority = self.priority_combo.currentData()
        state.provider_ready = self.provider_ready.isChecked()
        state.provider_profiles = self.provider_profiles.text().strip()
        state.framing_type = self.framing_type.text().strip()
        state.coverage = self.coverage.text().strip()
        state.required_features_visible = self.features_visible.isChecked()
        state.identity_visible = self.identity_visible.isChecked()
        state.full_required_asset_visible = self.full_asset_visible.isChecked()
        state.contains_subjects = self.contains_subjects.text().strip()
        state.contains_props = self.contains_props.text().strip()
        state.contains_environments = self.contains_environments.text().strip()
        state.review_note = self.review_note.toPlainText().strip()
        self._refresh_table_row(self._current_row)

    def _refresh_table_row(self, row: int) -> None:
        state = self._states[row]
        self.table.blockSignals(True)
        try:
            dimensions_item = self.table.item(row, 5)
            provider_ready_item = self.table.item(row, 6)
            role_item = self.table.item(row, 7)
            if dimensions_item is not None:
                dimensions_item.setText(self._dimensions_text(state))
            if provider_ready_item is not None:
                provider_ready_item.setText("Yes" if state.provider_ready else "No")
            if role_item is not None:
                role_item.setText(state.role.value)
        finally:
            self.table.blockSignals(False)

    def _add_helper(self) -> None:
        path_text, _filter = QFileDialog.getOpenFileName(
            self,
            "Select reviewed composition/helper reference",
            str(self.authoring.project_directory),
            "Images (*.png *.jpg *.jpeg *.webp);;All files (*)",
        )
        if not path_text:
            return
        width, height = self._image_dimensions(path_text)
        role = ReferenceRole.SCENE_COMPOSITION_ANCHOR
        state = _ReferenceState(
            included=True,
            asset_id=None,
            semantic_role="Composition / helper",
            category="multi_subject_scene",
            source_path=str(Path(path_text).resolve(strict=False)),
            canonical_source_id=None,
            reference_id=self.authoring.make_reference_id(
                asset_id=None,
                source_path=path_text,
                role=role,
            ),
            label=f"Shot composition — {self.package.shot_id}",
            role=role,
            reference_class=ReferenceClass.SHOT_COMPOSITE,
            subject_type=ReferenceSubjectType.MULTI_SUBJECT_SCENE,
            priority=ReferencePriority.REQUIRED,
            width=width,
            height=height,
            checksum=self._file_checksum_display(path_text, ""),
            provider_ready=False,
            provider_profiles=self.target_profile.text().strip(),
            framing_type="unknown",
            coverage="unknown",
            required_features_visible=False,
            identity_visible=False,
            full_required_asset_visible=False,
            contains_subjects="",
            contains_props="",
            contains_environments="",
            review_note="",
            custom=True,
        )
        self._states.append(state)
        self._populate_table()
        row = len(self._states) - 1
        self.table.selectRow(row)
        self._current_row = row
        self._load_editor(row)
        self._update_action_state()

    def _remove_helper(self) -> None:
        row = self._current_row
        if not (0 <= row < len(self._states)) or not self._states[row].custom:
            return
        del self._states[row]
        self._populate_table()
        if self._states:
            next_row = min(row, len(self._states) - 1)
            self.table.selectRow(next_row)
            self._current_row = next_row
            self._load_editor(next_row)
        else:
            self._current_row = -1
            self.preview.setText("No references")
        self._update_action_state()

    def _save_review(self) -> None:
        try:
            path = self.authoring.save_review(
                self.package,
                target=self._target(),
                references=self._selected_reviews(),
            )
        except (GovernedReferenceSuitabilityAuthoringError, ValueError) as exc:
            QMessageBox.warning(self, "Governed Reference Suitability Review", str(exc))
            return
        QMessageBox.information(
            self,
            "Governed Reference Suitability Review",
            f"Explicit suitability review saved:\n{path}\n\nNo provider execution occurred.",
        )

    def _approve(self) -> None:
        try:
            plan = self.authoring.approve_and_resolve(
                self.package,
                target=self._target(),
                references=self._selected_reviews(),
            )
        except (
            GovernedReferenceSuitabilityAuthoringError,
            GovernedReferenceSuitabilityError,
            ValueError,
        ) as exc:
            QMessageBox.warning(
                self,
                "Governed Reference Suitability Review",
                f"Suitability review did not produce a passing governed ReferencePlan:\n\n{exc}",
            )
            return
        QMessageBox.information(
            self,
            "Governed Reference Suitability Review",
            "Provider-ready suitability authority passed and the governed ReferencePlan was "
            f"persisted for {self.package.shot_id}.\n\nStatus: {plan.get('status', 'passed')}\n"
            "No provider execution occurred.",
        )
        self.accept()

    def _target(self) -> SuitabilityReviewTarget:
        return SuitabilityReviewTarget(
            width=self.target_width.value(),
            height=self.target_height.value(),
            profile_id=self.target_profile.text().strip(),
            provider_id=self.target_provider.text().strip() or None,
            aspect_tolerance=self.aspect_tolerance.value(),
        )

    def _selected_reviews(self) -> tuple[SuitabilityReferenceReview, ...]:
        reviews: list[SuitabilityReferenceReview] = []
        for state in self._states:
            if not state.included:
                continue
            reviews.append(
                SuitabilityReferenceReview(
                    reference_id=state.reference_id,
                    asset_id=state.asset_id,
                    role=state.role,
                    reference_class=state.reference_class,
                    subject_type=state.subject_type,
                    priority=state.priority,
                    source_path=state.source_path,
                    canonical_source_id=state.canonical_source_id,
                    label=state.label,
                    width=state.width,
                    height=state.height,
                    provider_ready=state.provider_ready,
                    provider_profiles=self._split_values(state.provider_profiles),
                    framing_type=state.framing_type,
                    coverage=state.coverage,
                    required_features_visible=state.required_features_visible,
                    identity_visible=state.identity_visible,
                    full_required_asset_visible=state.full_required_asset_visible,
                    contains_subjects=self._split_values(state.contains_subjects),
                    contains_props=self._split_values(state.contains_props),
                    contains_environments=self._split_values(state.contains_environments),
                    review_note=state.review_note,
                )
            )
        return tuple(reviews)

    def _update_action_state(self) -> None:
        current_custom = bool(
            0 <= self._current_row < len(self._states) and self._states[self._current_row].custom
        )
        self.remove_helper_button.setEnabled(current_custom)
        included = any(state.included for state in self._states)
        self.save_button.setEnabled(included)
        self.approve_button.setEnabled(included)

    def _show_preview(self, source_path: str) -> None:
        pixmap = QPixmap(source_path)
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("Preview unavailable")
            return
        scaled = pixmap.scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setText("")
        self.preview.setPixmap(scaled)

    @staticmethod
    def _image_dimensions(source_path: str) -> tuple[int, int]:
        reader = QImageReader(source_path)
        size = reader.size()
        if not size.isValid():
            return 0, 0
        return size.width(), size.height()

    @staticmethod
    def _file_checksum_display(source_path: str, fallback: str) -> str:
        path = Path(source_path)
        if not path.is_file():
            return fallback
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _select_enum(combo: QComboBox, value: Any) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

    @staticmethod
    def _enum_value(enum_type: Any, raw: object, default: Any) -> Any:
        try:
            return enum_type(str(raw or ""))
        except ValueError:
            return default

    @staticmethod
    def _join_values(value: object) -> str:
        if not isinstance(value, list | tuple):
            return ""
        return ", ".join(str(item).strip() for item in value if str(item).strip())

    @staticmethod
    def _split_values(value: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))

    @staticmethod
    def _positive_int(value: object, fallback: int) -> int:
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value > 0
            else fallback
        )

    @staticmethod
    def _path_key(value: str) -> str:
        return str(Path(value.replace("\\", "/")).resolve(strict=False)).casefold()

    @staticmethod
    def _dimensions_text(state: _ReferenceState) -> str:
        if state.width > 0 and state.height > 0:
            return f"{state.width}x{state.height}"
        return "Unknown"
