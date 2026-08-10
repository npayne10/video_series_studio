"""Behaviour Profile workspace for Phase 19.2.4."""

from __future__ import annotations

import json
from collections.abc import Callable

from pydantic import TypeAdapter, ValidationError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vscs.application.behaviours import (
    BehaviourGovernanceError,
    BehaviourProfileService,
    BehaviourProfileServiceError,
)
from vscs.domain.assets import AssetCategory
from vscs.domain.behaviours import (
    BehaviourAuthority,
    BehaviourCategory,
    BehaviourConstraint,
    BehaviourInteractionRequirement,
    BehaviourOutcome,
    BehaviourParameter,
    BehaviourPrecondition,
    BehaviourProfile,
    BehaviourProvenance,
)

_PARAMETERS = TypeAdapter(tuple[BehaviourParameter, ...])
_PRECONDITIONS = TypeAdapter(tuple[BehaviourPrecondition, ...])
_CONSTRAINTS = TypeAdapter(tuple[BehaviourConstraint, ...])
_OUTCOMES = TypeAdapter(tuple[BehaviourOutcome, ...])
_INTERACTIONS = TypeAdapter(tuple[BehaviourInteractionRequirement, ...])
_METADATA = TypeAdapter(dict[str, str])


class BehaviourProfileEditorDialog(QDialog):
    """Scrollable, resizable structured editor for one Behaviour Profile version."""

    def __init__(
        self, profile: BehaviourProfile | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.setObjectName("behaviourProfileEditorDialog")
        self.setWindowTitle("Behaviour Profile")
        self.setMinimumSize(680, 480)
        self.resize(900, 700)

        root = QVBoxLayout(self)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("behaviourProfileEditorScrollArea")
        self.scroll_area.setWidgetResizable(True)
        root.addWidget(self.scroll_area)

        body = QWidget(self.scroll_area)
        body_layout = QVBoxLayout(body)
        form = QFormLayout()
        self.profile_id_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.version_edit = QLineEdit("1.0")
        self.action_edit = QLineEdit()
        self.category_combo = QComboBox()
        for category in BehaviourCategory:
            self.category_combo.addItem(category.value.replace("_", " ").title(), category)
        self.description_edit = QPlainTextEdit()
        self.description_edit.setMaximumHeight(110)
        self.aliases_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.asset_categories = QListWidget()
        self.asset_categories.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.asset_categories.setMaximumHeight(150)
        for category in AssetCategory:
            item = QListWidgetItem(category.value.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.asset_categories.addItem(item)
        self.authority_label = QLabel(BehaviourAuthority.DRAFT.value.title())

        form.addRow("Profile ID", self.profile_id_edit)
        form.addRow("Name", self.name_edit)
        form.addRow("Version", self.version_edit)
        form.addRow("Category", self.category_combo)
        form.addRow("Action", self.action_edit)
        form.addRow("Applicable asset categories", self.asset_categories)
        form.addRow("Aliases (comma separated)", self.aliases_edit)
        form.addRow("Tags (comma separated)", self.tags_edit)
        form.addRow("Authority", self.authority_label)
        form.addRow("Description", self.description_edit)
        body_layout.addLayout(form)

        self.tabs = QTabWidget()
        self.parameters_edit = self._json_editor("Parameters", "[]")
        self.preconditions_edit = self._json_editor("Preconditions", "[]")
        self.constraints_edit = self._json_editor("Constraints", "[]")
        self.outcomes_edit = self._json_editor("Outcomes", "[]")
        self.interactions_edit = self._json_editor("Interactions", "[]")
        self.provenance_edit = self._json_editor("Provenance", "{}")
        self.metadata_edit = self._json_editor("Metadata", "{}")
        body_layout.addWidget(self.tabs)
        self.scroll_area.setWidget(body)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        if profile is not None:
            self._load(profile)

    def _json_editor(self, title: str, initial: str) -> QPlainTextEdit:
        editor = QPlainTextEdit(initial)
        editor.setObjectName(f"behaviour{title}Editor")
        editor.setMinimumHeight(150)
        self.tabs.addTab(editor, title)
        return editor

    def _load(self, profile: BehaviourProfile) -> None:
        self.profile_id_edit.setText(profile.profile_id)
        self.name_edit.setText(profile.name)
        self.version_edit.setText(profile.version)
        self.action_edit.setText(profile.action)
        self.description_edit.setPlainText(profile.description)
        self.aliases_edit.setText(", ".join(profile.aliases))
        self.tags_edit.setText(", ".join(profile.tags))
        self.authority_label.setText(profile.authority.value.title())
        self.category_combo.setCurrentIndex(self.category_combo.findData(profile.category))
        for row in range(self.asset_categories.count()):
            item = self.asset_categories.item(row)
            item.setSelected(
                item.data(Qt.ItemDataRole.UserRole) in profile.applicable_asset_categories
            )
        self.parameters_edit.setPlainText(self._dump(profile.parameters))
        self.preconditions_edit.setPlainText(self._dump(profile.preconditions))
        self.constraints_edit.setPlainText(self._dump(profile.constraints))
        self.outcomes_edit.setPlainText(self._dump(profile.outcomes))
        self.interactions_edit.setPlainText(self._dump(profile.interactions))
        self.provenance_edit.setPlainText(
            json.dumps(profile.provenance.model_dump(mode="json"), indent=2)
        )
        self.metadata_edit.setPlainText(json.dumps(profile.metadata, indent=2, sort_keys=True))

        # Persistent BEP identity is immutable after creation, including for Drafts.
        self.profile_id_edit.setEnabled(False)
        self.version_edit.setEnabled(False)

        governed = profile.authority is not BehaviourAuthority.DRAFT
        for widget in (
            self.name_edit,
            self.action_edit,
            self.description_edit,
            self.aliases_edit,
            self.tags_edit,
            self.asset_categories,
            self.category_combo,
            self.tabs,
        ):
            widget.setEnabled(not governed)
        save = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        if save is not None:
            save.setEnabled(not governed)

    @staticmethod
    def _dump(values: tuple[object, ...]) -> str:
        return json.dumps(
            [value.model_dump(mode="json") for value in values],  # type: ignore[attr-defined]
            indent=2,
        )

    @staticmethod
    def _terms(value: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))

    def build_profile(self) -> BehaviourProfile:
        categories = tuple(
            item.data(Qt.ItemDataRole.UserRole) for item in self.asset_categories.selectedItems()
        )
        authority = self.profile.authority if self.profile is not None else BehaviourAuthority.DRAFT
        schema_version = self.profile.schema_version if self.profile is not None else 1
        try:
            parameters = _PARAMETERS.validate_python(
                json.loads(self.parameters_edit.toPlainText() or "[]")
            )
            preconditions = _PRECONDITIONS.validate_python(
                json.loads(self.preconditions_edit.toPlainText() or "[]")
            )
            constraints = _CONSTRAINTS.validate_python(
                json.loads(self.constraints_edit.toPlainText() or "[]")
            )
            outcomes = _OUTCOMES.validate_python(
                json.loads(self.outcomes_edit.toPlainText() or "[]")
            )
            interactions = _INTERACTIONS.validate_python(
                json.loads(self.interactions_edit.toPlainText() or "[]")
            )
            provenance_raw = json.loads(self.provenance_edit.toPlainText() or "{}")
            metadata_raw = json.loads(self.metadata_edit.toPlainText() or "{}")
            provenance = BehaviourProvenance.model_validate(provenance_raw)
            metadata = _METADATA.validate_python(metadata_raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"Invalid structured Behaviour Profile data: {exc}") from exc

        return BehaviourProfile(
            schema_version=schema_version,
            profile_id=self.profile_id_edit.text(),
            name=self.name_edit.text(),
            version=self.version_edit.text(),
            description=self.description_edit.toPlainText(),
            category=self.category_combo.currentData(),
            action=self.action_edit.text(),
            applicable_asset_categories=categories,
            aliases=self._terms(self.aliases_edit.text()),
            parameters=parameters,
            preconditions=preconditions,
            constraints=constraints,
            outcomes=outcomes,
            interactions=interactions,
            tags=self._terms(self.tags_edit.text()),
            authority=authority,
            provenance=provenance,
            metadata=metadata,
        )


class BehaviourProfileManagerWidget(QWidget):
    """Workspace for browsing, editing and governing Behaviour Profiles."""

    def __init__(
        self,
        service: BehaviourProfileService,
        parent: QWidget | None = None,
        *,
        project_available: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.project_available = project_available or (lambda: True)
        self.setObjectName("behaviourProfileManager")
        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search behaviours...")
        self.category_filter = QComboBox()
        self.category_filter.addItem("All categories", None)
        for category in BehaviourCategory:
            self.category_filter.addItem(category.value.replace("_", " ").title(), category)
        self.authority_filter = QComboBox()
        self.authority_filter.addItem("All authority", None)
        for authority in BehaviourAuthority:
            self.authority_filter.addItem(authority.value.title(), authority)
        filters.addWidget(self.search_edit, 1)
        filters.addWidget(self.category_filter)
        filters.addWidget(self.authority_filter)
        layout.addLayout(filters)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("behaviourProfileTable")
        self.table.setHorizontalHeaderLabels(
            ["Profile ID", "Version", "Name", "Category", "Action", "Authority"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.edit_button = QPushButton("Edit / View")
        self.delete_button = QPushButton("Delete Draft")
        self.submit_button = QPushButton("Submit")
        self.rework_button = QPushButton("Return to Draft")
        self.approve_button = QPushButton("Approve")
        self.canonical_button = QPushButton("Make Canonical")
        self.revise_button = QPushButton("New Revision")
        self.refresh_button = QPushButton("Refresh")
        for button in (
            self.new_button,
            self.edit_button,
            self.delete_button,
            self.submit_button,
            self.rework_button,
            self.approve_button,
            self.canonical_button,
            self.revise_button,
            self.refresh_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.search_edit.textChanged.connect(self.refresh)
        self.category_filter.currentIndexChanged.connect(self.refresh)
        self.authority_filter.currentIndexChanged.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.new_button.clicked.connect(self._new)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.submit_button.clicked.connect(lambda: self._transition(BehaviourAuthority.PROPOSED))
        self.rework_button.clicked.connect(lambda: self._transition(BehaviourAuthority.DRAFT))
        self.approve_button.clicked.connect(lambda: self._transition(BehaviourAuthority.APPROVED))
        self.canonical_button.clicked.connect(
            lambda: self._transition(BehaviourAuthority.CANONICAL)
        )
        self.revise_button.clicked.connect(self._revise)
        self.refresh_button.clicked.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        if not self.project_available():
            self.table.setRowCount(0)
            self._update_actions()
            return
        try:
            profiles = self.service.list(
                query=self.search_edit.text(),
                category=self.category_filter.currentData(),
                authority=self.authority_filter.currentData(),
            )
        except BehaviourProfileServiceError:
            profiles = ()
        self.table.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            values = (
                profile.profile_id,
                profile.version,
                profile.name,
                profile.category.value,
                profile.action,
                profile.authority.value,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, (profile.profile_id, profile.version))
                self.table.setItem(row, column, item)
        self._update_actions()

    def _selected(self) -> BehaviourProfile | None:
        row = self.table.currentRow()
        if row < 0 or not self.project_available():
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        profile_id, version = item.data(Qt.ItemDataRole.UserRole)
        try:
            return self.service.get(profile_id, version)
        except BehaviourProfileServiceError:
            return None

    def _update_actions(self) -> None:
        profile = self._selected()
        selected = profile is not None
        self.edit_button.setEnabled(selected)
        self.revise_button.setEnabled(selected)
        self.delete_button.setEnabled(
            selected and profile.authority is BehaviourAuthority.DRAFT if profile else False
        )
        self.submit_button.setEnabled(
            selected and profile.authority is BehaviourAuthority.DRAFT if profile else False
        )
        self.rework_button.setEnabled(
            selected and profile.authority is BehaviourAuthority.PROPOSED if profile else False
        )
        self.approve_button.setEnabled(
            selected and profile.authority is BehaviourAuthority.PROPOSED if profile else False
        )
        self.canonical_button.setEnabled(
            selected and profile.authority is BehaviourAuthority.APPROVED if profile else False
        )

    def _run_dialog(
        self, profile: BehaviourProfile | None, persist: Callable[[BehaviourProfile], object]
    ) -> None:
        dialog = BehaviourProfileEditorDialog(profile, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            built = dialog.build_profile()
            persist(built)
        except (ValueError, ValidationError, BehaviourProfileServiceError) as exc:
            QMessageBox.critical(self, "Behaviour Profile", str(exc))
            return
        self.refresh()

    def _new(self) -> None:
        if self.project_available():
            self._run_dialog(None, self.service.create)

    def _edit(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        if profile.authority is BehaviourAuthority.DRAFT:
            self._run_dialog(profile, self.service.update_draft)
        else:
            BehaviourProfileEditorDialog(profile, self).exec()

    def _delete(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        if (
            QMessageBox.question(self, "Delete Draft", "Delete this draft Behaviour Profile?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.service.delete_draft(profile.profile_id, profile.version)
        except BehaviourProfileServiceError as exc:
            QMessageBox.critical(self, "Behaviour Profile", str(exc))
        self.refresh()

    def _transition(self, target: BehaviourAuthority) -> None:
        profile = self._selected()
        if profile is None:
            return
        try:
            self.service.transition(profile.profile_id, profile.version, target)
        except BehaviourGovernanceError as exc:
            QMessageBox.warning(self, "Behaviour Governance", str(exc))
        except BehaviourProfileServiceError as exc:
            QMessageBox.critical(self, "Behaviour Profile", str(exc))
        self.refresh()

    def _revise(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        version, accepted = QInputDialog.getText(
            self,
            "New Behaviour Revision",
            "New version:",
        )
        if not accepted or not version.strip():
            return
        try:
            self.service.revise(profile.profile_id, profile.version, version.strip())
        except BehaviourProfileServiceError as exc:
            QMessageBox.critical(self, "Behaviour Profile", str(exc))
        self.refresh()
