"""CAP to Behaviour Profile linkage UI for Phase 19.2.5."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps import CAPBehaviourIntegrationError, CAPBehaviourIntegrationService
from vscs.presentation.widgets.cap_manager import CAPManagerWidget


class CAPBehaviourProfilesDialog(QDialog):
    """Select production-authoritative Behaviour Profile identities for one CAP."""

    def __init__(
        self,
        integration: CAPBehaviourIntegrationService,
        asset_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.integration = integration
        self.asset_id = asset_id
        self.setObjectName("capBehaviourProfilesDialog")
        self.setWindowTitle(f"Behaviour Profiles — {asset_id}")
        self.setMinimumSize(680, 480)
        self.resize(820, 620)

        explanation = QLabel(
            "Select the governed behaviours this Canonical Asset Profile can perform. "
            "CAPs store stable BEP identities; production resolves each identity to its "
            "current Canonical or Approved version."
        )
        explanation.setWordWrap(True)

        self.profiles = QListWidget()
        self.profiles.setObjectName("capBehaviourProfileList")
        self.profiles.setAlternatingRowColors(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addWidget(self.profiles, 1)
        layout.addWidget(buttons)

        self._load()

    def selected_profile_ids(self) -> tuple[str, ...]:
        """Return checked BEP identities in deterministic display order."""
        selected: list[str] = []
        for row in range(self.profiles.count()):
            item = self.profiles.item(row)
            if item.checkState() is Qt.CheckState.Checked:
                profile_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(profile_id, str):
                    selected.append(profile_id)
        return tuple(selected)

    def _load(self) -> None:
        cap = self.integration.caps.get(self.asset_id)
        linked = set(cap.behaviour_references)
        available = self.integration.available_for_cap(self.asset_id)
        available_ids = {profile.profile_id for profile in available}

        for profile in available:
            item = QListWidgetItem(
                f"{profile.profile_id} — {profile.name}  "
                f"[v{profile.version}, {profile.authority.value}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, profile.profile_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if profile.profile_id in linked else Qt.CheckState.Unchecked
            )
            item.setToolTip(profile.description or profile.action)
            self.profiles.addItem(item)

        for profile_id in sorted(linked - available_ids):
            item = QListWidgetItem(
                f"{profile_id} — unavailable or incompatible (will be removed if saved)"
            )
            item.setData(Qt.ItemDataRole.UserRole, profile_id)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.profiles.addItem(item)

    def _save(self) -> None:
        try:
            self.integration.set_behaviours(self.asset_id, self.selected_profile_ids())
        except CAPBehaviourIntegrationError as exc:
            QMessageBox.warning(self, "Behaviour Profile Link", str(exc))
            return
        self.accept()


def install_cap_behaviour_profiles(
    manager: CAPManagerWidget,
    integration: CAPBehaviourIntegrationService,
) -> QPushButton:
    """Install the Phase 19.2.5 BEP linkage action into the CAP workspace."""
    button = QPushButton("Behaviour Profiles…", manager)
    button.setObjectName("capBehaviourProfilesButton")
    button.setToolTip("Link production-authoritative Behaviour Profiles to the selected CAP")
    button.setEnabled(False)

    root_layout = manager.layout()
    if root_layout is not None and root_layout.count() > 0:
        first_item = root_layout.itemAt(0)
        if first_item is not None:
            controls = first_item.layout()
            if isinstance(controls, QHBoxLayout):
                controls.insertWidget(max(0, controls.count() - 1), button)

    def update_enabled() -> None:
        button.setEnabled(manager._selected_asset_id() is not None)

    def open_dialog() -> None:
        asset_id = manager._selected_asset_id()
        if asset_id is None:
            return
        try:
            dialog = CAPBehaviourProfilesDialog(integration, asset_id, manager)
        except Exception as exc:
            QMessageBox.critical(manager, "Behaviour Profile Link", str(exc))
            return
        if dialog.exec() == QDialog.DialogCode.Accepted:
            manager.refresh()
            update_enabled()

    manager.table.itemSelectionChanged.connect(update_enabled)
    button.clicked.connect(open_dialog)
    return button
